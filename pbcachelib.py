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

# Redis client (initialized later after config is available)
rc = None
CACHE_KEY = "puzzleboss:all"
CACHE_TTL = 15  # seconds
LASTACT_KEY = "puzzleboss:lastact"
LOCK_KEY = "puzzleboss:all:lock"
LOCK_TTL = 5  # seconds — bounds how long a crashed rebuilder blocks others

# Flag to track if the cache client has been initialized
_cache_initialized = False


def init_cache(configstruct):
    """Initialize Redis client from config. Call after DB config is loaded."""
    global rc
    if not REDIS_AVAILABLE:
        debug_log(3, "Cache: redis-py not installed")
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
        if value:
            debug_log(5, f"cache_get: hit for {key}")
        return value
    except Exception as e:
        debug_log(3, f"cache_get error: {e}")
        return None


def cache_set(key, value, ttl=CACHE_TTL):
    """Safe cache set - fails silently if disabled"""
    if rc is None:
        return
    try:
        rc.set(key, value, ex=ttl)
        debug_log(5, f"cache_set: stored {key}")
    except Exception as e:
        debug_log(3, f"cache_set error: {e}")


def cache_delete(key):
    """Safe cache delete - fails silently if disabled"""
    if rc is None:
        return
    try:
        rc.delete(key)
        debug_log(5, f"cache_delete: deleted {key}")
    except Exception as e:
        debug_log(3, f"cache_delete error: {e}")


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
    except Exception as e:
        debug_log(3, f"lastact_set error: {e}")


def lastact_get_all():
    """Return {puzzle_id (int): activity_row (dict)} from the lastact hash.

    Returns None (not {}) when Redis is unavailable so callers can
    distinguish "cache down — use the DB" from "no activity yet".
    """
    if rc is None:
        return None
    try:
        raw = rc.hgetall(LASTACT_KEY)
        return {int(pid): json.loads(val) for pid, val in raw.items()}
    except Exception as e:
        debug_log(3, f"lastact_get_all error: {e}")
        return None


def lastact_get(puzzle_id):
    """Return one puzzle's latest activity row from the hash, or None."""
    if rc is None:
        return None
    try:
        raw = rc.hget(LASTACT_KEY, str(int(puzzle_id)))
        return json.loads(raw) if raw else None
    except Exception as e:
        debug_log(3, f"lastact_get error: {e}")
        return None


def lastact_delete(puzzle_id):
    """Remove a puzzle from the lastact hash (call on puzzle deletion)."""
    if rc is None:
        return
    try:
        rc.hdel(LASTACT_KEY, str(int(puzzle_id)))
    except Exception as e:
        debug_log(3, f"lastact_delete error: {e}")


def lastact_set_many(rows_by_pid):
    """Bulk-populate the lastact hash (cold-start backfill from the DB)."""
    if rc is None or not rows_by_pid:
        return
    try:
        rc.hset(
            LASTACT_KEY,
            mapping={str(int(pid)): json.dumps(row) for pid, row in rows_by_pid.items()},
        )
        debug_log(4, f"lastact_set_many: backfilled {len(rows_by_pid)} puzzles")
    except Exception as e:
        debug_log(3, f"lastact_set_many error: {e}")


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
        return bool(rc.set(LOCK_KEY, "1", nx=True, ex=LOCK_TTL))
    except Exception as e:
        debug_log(3, f"rebuild lock error: {e}")
        return True


def release_rebuild_lock():
    if rc is None:
        return
    try:
        rc.delete(LOCK_KEY)
    except Exception as e:
        debug_log(3, f"rebuild lock release error: {e}")


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
    """Initialize the Redis client from DB config on first use."""
    # Note: No lock needed — concurrent initialization is harmless since both
    # workers would read the same config and create equivalent clients.
    global _cache_initialized
    if _cache_initialized:
        return
    _cache_initialized = True

    try:
        # Query config from database
        cursor = conn.cursor()
        cursor.execute("SELECT `key`, `val` FROM config WHERE `key` LIKE 'REDIS_%'")
        rows = cursor.fetchall()
        cache_config = {row["key"]: row["val"] for row in rows}
        init_cache(cache_config)
    except Exception as e:
        debug_log(2, f"Failed to load Redis config from database: {e}")
