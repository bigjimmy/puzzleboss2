"""
PuzzleBoss Cache Library - Redis operations

This module provides Redis-backed caching:

- The /all response blob (``CACHE_KEY``): structural rounds/puzzles data,
  15s TTL, invalidated only on structural changes (see pblib's allowlist).
- The lastact hash (``LASTACT_KEY``): one field per puzzle id holding the
  puzzle's most recent activity row as JSON. Write-through: updated in place
  by pblib.log_activity() on every activity insert, never invalidated.
- A rebuild lock (``LOCK_KEY``): SET NX guard so concurrent /all cache
  misses produce one rebuild instead of a stampede.

All operations are fail-safe: if Redis is unavailable they return None /
no-op and the caller falls through to the database.
"""

import json

from pblib import debug_log, increment_botstat

# Optional redis support
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    debug_log(3, "redis-py not installed - caching disabled")

# Tracks whether the last Redis operation succeeded, so we log one SEV2 line
# per worker on the working→down transition (and a SEV3 line on recovery)
# instead of a flood of identical per-request errors. None = no op attempted
# yet. Per-process state (Gunicorn sync workers): expect up to one transition
# log per worker, not one per cluster.
_redis_healthy = None


def _note_redis_error(where, exc):
    """Log a Redis I/O error. Warn (SEV2) on the first failure after health,
    then drop to SEV3 for subsequent failures to avoid flooding while down."""
    global _redis_healthy
    if _redis_healthy is not False:
        debug_log(2, f"Redis unavailable ({where}): {exc} — falling back to DB")
        _redis_healthy = False
    else:
        debug_log(3, f"{where} error: {exc}")


def _note_redis_ok():
    """Mark a successful Redis op; log recovery once on down→working."""
    global _redis_healthy
    if _redis_healthy is False:
        debug_log(3, "Redis recovered — cache operations succeeding again")
    _redis_healthy = True


def _incr(stat):
    """Fail-safe counter bump that opens its own short-lived DB connection.
    Used for cache metrics on paths that don't already hold a conn. Never
    raises — a stats failure must not affect the cache operation."""
    try:
        from pblib import create_db_connection

        conn = create_db_connection()
        try:
            increment_botstat(stat, conn)
        finally:
            conn.close()
    except Exception as e:
        debug_log(3, f"failed to increment {stat}: {e}")


# Redis client (initialized later after config is available)
rc = None
CACHE_KEY = "puzzleboss:all"
CACHE_TTL = 15  # seconds
LASTACT_KEY = "puzzleboss:lastact"
LOCK_KEY = "puzzleboss:all:lock"
LOCK_TTL = 5  # seconds — bounds how long a crashed rebuilder blocks others

# Flag to track if the cache client has been successfully initialized.
# Latched only on a working connection; see ensure_cache_initialized.
_cache_initialized = False
_last_init_attempt = None
_INIT_RETRY_INTERVAL = 30  # seconds — retry cadence while cache is disabled/down


def init_cache(configstruct):
    """Initialize Redis client from config. Call after DB config is loaded."""
    global rc
    if not REDIS_AVAILABLE:
        # Already logged once at import; stay quiet here to avoid duplication.
        return

    try:
        enabled = configstruct.get("REDIS_ENABLED", "false").lower() == "true"
        host = configstruct.get("REDIS_HOST", "")
        port = int(configstruct.get("REDIS_PORT", 6379))

        if not enabled:
            debug_log(3, "Cache: disabled in config")
            return

        if not host:
            debug_log(3, "Cache: no Redis host configured")
            return

        rc = redis.Redis(
            host=host,
            port=port,
            decode_responses=True,
            socket_timeout=1,
            socket_connect_timeout=1,
        )
        # Test connection
        rc.set("_test", "ok", ex=1)
        debug_log(3, f"Cache: Redis initialized successfully ({host}:{port})")
    except Exception as e:
        debug_log(2, f"Cache: failed to initialize Redis: {e}")
        rc = None


def cache_get(key):
    """Safe cache get - returns None on error or if disabled"""
    if rc is None:
        return None
    try:
        value = rc.get(key)
        debug_log(5, f"cache_get: {'hit' if value else 'miss'} for {key}")
        _note_redis_ok()
        return value
    except Exception as e:
        _note_redis_error("cache_get", e)
        return None


def cache_set(key, value, ttl=CACHE_TTL):
    """Safe cache set - fails silently if disabled"""
    if rc is None:
        return
    try:
        rc.set(key, value, ex=ttl)
        debug_log(5, f"cache_set: stored {key}")
        _note_redis_ok()
    except Exception as e:
        _note_redis_error("cache_set", e)


def cache_delete(key):
    """Safe cache delete - fails silently if disabled"""
    if rc is None:
        return
    try:
        rc.delete(key)
        debug_log(5, f"cache_delete: deleted {key}")
        _note_redis_ok()
    except Exception as e:
        _note_redis_error("cache_delete", e)


# ── lastact write-through hash ────────────────────────────────────────────


def lastact_set(puzzle_id, activity_row):
    """Write-through a puzzle's latest activity row to the lastact hash.

    activity_row must already be JSON-safe (time as ISO 8601 string).
    Fail-safe: a missed write leaves that puzzle's entry stale until its
    next activity; readers self-heal via the DB fallback in pbrest.
    """
    if rc is None:
        return
    try:
        rc.hset(LASTACT_KEY, str(int(puzzle_id)), json.dumps(activity_row))
        debug_log(5, f"lastact_set: puzzle {puzzle_id}")
        _note_redis_ok()
    except Exception as e:
        _note_redis_error("lastact_set", e)
        _incr("cache_write_through_failures_total")


def lastact_get_all():
    """Return {puzzle_id (int): activity_row (dict)} from the lastact hash.

    Returns None (not {}) when Redis is unavailable so callers can
    distinguish "cache down — use the DB" from "no activity yet".
    """
    if rc is None:
        return None
    try:
        raw = rc.hgetall(LASTACT_KEY)
        _note_redis_ok()
    except Exception as e:
        _note_redis_error("lastact_get_all", e)
        return None
    # Decode per-item so one corrupt entry degrades only that puzzle (to a DB
    # fallback in pbrest), not all of them. A malformed value here is a
    # data-quality issue, not a Redis-down condition, so don't return None.
    result = {}
    for pid, val in raw.items():
        try:
            result[int(pid)] = json.loads(val)
        except (ValueError, TypeError) as e:
            debug_log(2, f"lastact_get_all: skipping corrupt entry for pid {pid!r}: {e}")
    return result


def lastact_get(puzzle_id):
    """Return one puzzle's latest activity row from the hash, or None."""
    if rc is None:
        return None
    try:
        raw = rc.hget(LASTACT_KEY, str(int(puzzle_id)))
        _note_redis_ok()
        return json.loads(raw) if raw else None
    except Exception as e:
        _note_redis_error("lastact_get", e)
        return None


def lastact_delete(puzzle_id):
    """Remove a puzzle from the lastact hash (call on puzzle deletion)."""
    if rc is None:
        return
    try:
        rc.hdel(LASTACT_KEY, str(int(puzzle_id)))
        debug_log(5, f"lastact_delete: puzzle {puzzle_id}")
        _note_redis_ok()
    except Exception as e:
        _note_redis_error("lastact_delete", e)


def lastact_set_many(rows_by_pid):
    """Bulk-populate the lastact hash (cold-start backfill from the DB).

    A cold-start backfill means the hash was empty (Redis flushed/restarted or
    freshly deployed) and the /all read fell back to the DB GROUP BY. Logged at
    SEV3 and counted so the recovery is visible in production.
    """
    if rc is None or not rows_by_pid:
        return
    try:
        rc.hset(
            LASTACT_KEY,
            mapping={str(int(pid)): json.dumps(row) for pid, row in rows_by_pid.items()},
        )
        debug_log(3, f"lastact cold-start backfill: {len(rows_by_pid)} puzzles from DB")
        _note_redis_ok()
        _incr("cache_cold_start_backfills_total")
    except Exception as e:
        _note_redis_error("lastact_set_many", e)


# ── rebuild stampede lock ─────────────────────────────────────────────────


def try_acquire_rebuild_lock():
    """Try to become the one worker rebuilding the /all blob.

    Returns True if acquired (caller rebuilds and cache_sets), False if
    another worker holds it (caller serves from the DB without caching).
    With Redis down, returns True — everyone rebuilds, same as no cache.
    """
    if rc is None:
        return True
    try:
        acquired = bool(rc.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL))
        _note_redis_ok()
        return acquired
    except Exception as e:
        # Redis errored — fail open (caller rebuilds without the lock).
        _note_redis_error("rebuild lock", e)
        return True


def release_rebuild_lock():
    if rc is None:
        return
    try:
        rc.delete(LOCK_KEY)
    except Exception as e:
        _note_redis_error("rebuild lock release", e)


# ── lifecycle ─────────────────────────────────────────────────────────────


def invalidate_all_cache(conn):
    """Invalidate the /all blob. Call ONLY for structural changes (puzzle
    create/delete, round create/update/delete, status transitions) — see
    STRUCTURAL_PUZZLE_FIELDS in pblib. The lastact hash is write-through
    and is never invalidated.

    Counts every call in the cache_invalidations_total botstat. This is the
    single chokepoint for blob deletion, so all invalidation paths are
    counted. increment_botstat is fail-safe: a stats failure never blocks
    the invalidation.
    """
    ensure_cache_initialized(conn)
    cache_delete(CACHE_KEY)
    # The delete is the job; the counter is best-effort. Guard locally so the
    # "stats failure never blocks the invalidation" contract holds here rather
    # than depending on increment_botstat's internal error handling.
    try:
        increment_botstat("cache_invalidations_total", conn)
    except Exception as e:
        debug_log(3, f"cache invalidation stat increment failed: {e}")


def ensure_cache_initialized(conn):
    """Initialize the Redis client from DB config.

    Latches only on a *successful* connection (rc is not None). If the cache
    is disabled or Redis is unreachable, a later call retries — but no more
    than once per _INIT_RETRY_INTERVAL seconds, so a disabled cache doesn't
    re-query config on every request. This lets a config change (e.g.
    flipping REDIS_ENABLED=true during a cutover) take effect without a
    worker restart.
    """
    # No lock needed: Gunicorn sync workers are separate processes, so these
    # module globals are per-process and never contended. (If ever switching to
    # gevent/eventlet workers, where coroutines share a process, add a
    # threading.Lock around the global mutations below.)
    global _cache_initialized, _last_init_attempt
    if _cache_initialized:
        return

    import time
    now = time.time()
    if _last_init_attempt is not None and (now - _last_init_attempt) < _INIT_RETRY_INTERVAL:
        return
    _last_init_attempt = now

    try:
        # Query config from database
        cursor = conn.cursor()
        cursor.execute("SELECT `key`, `val` FROM config WHERE `key` LIKE 'REDIS_%'")
        rows = cursor.fetchall()
        cache_config = {row["key"]: row["val"] for row in rows}
        init_cache(cache_config)
    except Exception as e:
        debug_log(2, f"Failed to load Redis config from database: {e}")

    # Latch only once we actually have a working client; otherwise allow a
    # retry on a later call (rate-limited above).
    if rc is not None:
        _cache_initialized = True
