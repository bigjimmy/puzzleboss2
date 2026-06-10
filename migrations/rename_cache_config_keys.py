"""
Rename MEMCACHE_* config keys to REDIS_* for the Redis cache migration.

Background:
    The cache layer (pbcachelib.py) moved from memcache to Redis and reads
    REDIS_ENABLED / REDIS_HOST / REDIS_PORT from the config table. This
    migration renames the old keys in place, preserving ENABLED/HOST values.
    A port value of 11211 (the memcache default) is rewritten to 6379;
    any other explicit port is preserved.

    Run during the Redis cutover (REDIS_MIGRATION.md Phase 3), then update
    REDIS_HOST to the Redis service hostname.

Idempotent: safe to re-run. Each key is renamed only if the old key exists
and the new key does not.
"""

name = "rename_cache_config_keys"
description = "Rename MEMCACHE_ENABLED/HOST/PORT config keys to REDIS_ENABLED/HOST/PORT"

RENAMES = [
    ("MEMCACHE_ENABLED", "REDIS_ENABLED"),
    ("MEMCACHE_HOST", "REDIS_HOST"),
    ("MEMCACHE_PORT", "REDIS_PORT"),
]


def run(conn):
    """Rename cache config keys. Returns (success, message)."""
    cursor = conn.cursor()
    actions = []

    for old_key, new_key in RENAMES:
        cursor.execute("SELECT val FROM config WHERE `key` = %s", (old_key,))
        old_row = cursor.fetchone()
        cursor.execute("SELECT val FROM config WHERE `key` = %s", (new_key,))
        new_row = cursor.fetchone()

        if new_row is not None:
            actions.append(f"{new_key} already exists, skipped")
            continue
        if old_row is None:
            actions.append(f"{old_key} not found, skipped")
            continue

        cursor.execute(
            "UPDATE config SET `key` = %s WHERE `key` = %s", (new_key, old_key)
        )
        actions.append(f"renamed {old_key} -> {new_key}")

    # Memcache's default port makes no sense for Redis; swap it for Redis's.
    cursor.execute(
        "UPDATE config SET val = '6379' WHERE `key` = 'REDIS_PORT' AND val = '11211'"
    )
    if cursor.rowcount:
        actions.append("REDIS_PORT 11211 -> 6379")

    conn.commit()
    return True, "; ".join(actions)
