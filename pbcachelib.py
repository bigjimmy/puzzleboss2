"""
PuzzleBoss Cache Library - Memcache operations

This module provides memcache functionality for caching API responses.
Uses pymemcache with fail-safe operations (silently fails if cache unavailable).
"""

from pblib import debug_log

# Optional memcache support
try:
    from pymemcache.client import base as memcache_client

    MEMCACHE_AVAILABLE = True
except ImportError:
    MEMCACHE_AVAILABLE = False
    debug_log(3, "pymemcache not installed - caching disabled")

# Memcache client (initialized later after config is available)
mc = None
MEMCACHE_CACHE_KEY = "puzzleboss:all"
MEMCACHE_TTL = 15  # seconds

# Flag to track if memcache has been initialized
_memcache_initialized = False


def init_memcache(configstruct):
    """Initialize memcache client from config. Call after DB config is loaded."""
    global mc
    if not MEMCACHE_AVAILABLE:
        debug_log(3, "Memcache: pymemcache not installed")
        return

    try:
        enabled = configstruct.get("MEMCACHE_ENABLED", "false").lower() == "true"
        host = configstruct.get("MEMCACHE_HOST", "")
        port = int(configstruct.get("MEMCACHE_PORT", 11211))

        if not enabled:
            debug_log(3, "Memcache: disabled in config")
            return

        if not host:
            debug_log(3, "Memcache: no host configured")
            return

        mc = memcache_client.Client((host, port), timeout=1, connect_timeout=1)
        # Test connection
        mc.set("_test", "ok", expire=1)
        debug_log(3, f"Memcache: initialized successfully ({host}:{port})")
    except Exception as e:
        debug_log(2, f"Memcache: failed to initialize: {e}")
        mc = None


def cache_get(key):
    """Safe cache get - returns None on error or if disabled"""
    if mc is None:
        return None
    try:
        value = mc.get(key)
        if value:
            debug_log(5, f"cache_get: hit for {key}")
        return value
    except Exception as e:
        debug_log(3, f"cache_get error: {e}")
        return None


def cache_set(key, value, ttl=MEMCACHE_TTL):
    """Safe cache set - fails silently if disabled"""
    if mc is None:
        return
    try:
        mc.set(key, value, expire=ttl)
        debug_log(5, f"cache_set: stored {key}")
    except Exception as e:
        debug_log(3, f"cache_set error: {e}")


def cache_delete(key):
    """Safe cache delete - fails silently if disabled"""
    if mc is None:
        return
    try:
        mc.delete(key)
        debug_log(5, f"cache_delete: deleted {key}")
    except Exception as e:
        debug_log(3, f"cache_delete error: {e}")


def invalidate_all_cache(conn):
    """Invalidate the /all cache. Call when puzzle/round data changes.

    Note: This only invalidates the cache. If you want to track cache invalidation
    stats, call increment_botstat() from pblib separately with proper error handling.
    """
    ensure_memcache_initialized(conn)
    cache_delete(MEMCACHE_CACHE_KEY)


def ensure_memcache_initialized(conn):
    """Initialize memcache from DB config on first use."""
    # Note: No lock needed — concurrent initialization is harmless since both
    # workers would read the same config and create equivalent clients.
    global _memcache_initialized
    if _memcache_initialized:
        return
    _memcache_initialized = True

    try:
        # Query config from database
        cursor = conn.cursor()
        cursor.execute("SELECT `key`, `val` FROM config WHERE `key` LIKE 'MEMCACHE_%'")
        rows = cursor.fetchall()
        mc_config = {row["key"]: row["val"] for row in rows}
        init_memcache(mc_config)
    except Exception as e:
        debug_log(2, f"Failed to load memcache config from database: {e}")
