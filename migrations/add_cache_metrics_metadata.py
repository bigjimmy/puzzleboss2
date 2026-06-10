"""
Add the cache observability counters to METRICS_METADATA.

Background:
    The memcache→Redis migration dropped the hit/miss counters: the old
    memcache code incremented cache_hits_total / cache_misses_total, but the
    Redis rewrite lost those increments, leaving the Grafana "Cache HitRate"
    panel without data. The app now re-increments them (pbrest._get_all_with_cache)
    and also exposes new Redis-specific counters (write-through failures,
    rebuild-lock contention, cold-start backfills).

    METRICS_METADATA (config table) drives www/metrics.php: only keys listed
    there get HELP/TYPE headers in the Prometheus export. Fresh installs get
    these via scripts/puzzleboss.sql; this migration adds them to an existing
    (upgraded) production config.

Idempotent: safe to re-run. Only adds metrics that are missing; preserves any
existing entries and ordering.
"""

import json

name = "add_cache_metrics_metadata"
description = "Add cache hit/miss and Redis observability counters to METRICS_METADATA"

NEW_METRICS = {
    "cache_hits_total": {
        "type": "counter",
        "description": "Total /all cache hits (blob served from Redis)",
    },
    "cache_misses_total": {
        "type": "counter",
        "description": "Total /all cache misses (rebuilt from DB)",
    },
    "cache_write_through_failures_total": {
        "type": "counter",
        "description": "Total lastact write-through failures to Redis",
    },
    "cache_rebuild_lock_contentions_total": {
        "type": "counter",
        "description": "Total /all rebuilds served from DB without caching due to rebuild-lock contention",
    },
    "cache_cold_start_backfills_total": {
        "type": "counter",
        "description": "Total lastact hash cold-start backfills from DB (Redis flush/restart)",
    },
}

# Also refresh the invalidations description to match the schema seed.
UPDATED_DESCRIPTIONS = {
    "cache_invalidations_total": "Total /all blob cache invalidations (structural mutations)",
}


def run(conn):
    """Add cache metrics to METRICS_METADATA. Returns (success, message)."""
    cursor = conn.cursor()
    cursor.execute("SELECT val FROM config WHERE `key` = 'METRICS_METADATA'")
    row = cursor.fetchone()
    if not row or not row["val"]:
        return False, "METRICS_METADATA config row not found"

    try:
        metadata = json.loads(row["val"])
    except Exception as e:
        return False, f"METRICS_METADATA is not valid JSON: {e}"

    added = []
    for key, meta in NEW_METRICS.items():
        if key not in metadata:
            metadata[key] = meta
            added.append(key)

    updated = []
    for key, desc in UPDATED_DESCRIPTIONS.items():
        if key in metadata and metadata[key].get("description") != desc:
            metadata[key]["description"] = desc
            updated.append(key)

    if not added and not updated:
        return True, "All cache metrics already present, nothing to do"

    cursor.execute(
        "UPDATE config SET val = %s WHERE `key` = 'METRICS_METADATA'",
        (json.dumps(metadata),),
    )
    conn.commit()

    parts = []
    if added:
        parts.append(f"added {len(added)}: {', '.join(added)}")
    if updated:
        parts.append(f"updated descriptions: {', '.join(updated)}")
    return True, "; ".join(parts)
