"""
Rename bigjimmy botstats keys to include the bigjimmy_ prefix.

Background:
    bigjimmybot.py previously wrote metrics to the botstats table using short
    keys (e.g. "loop_time_seconds"), while METRICS_METADATA used a separate
    "db_key" field to map them to Prometheus metric names with the bigjimmy_
    prefix.  Now bigjimmybot writes the full prefixed key directly, so the
    botstats rows and METRICS_METADATA config key names match 1:1.

    This migration renames existing botstats rows and strips any remaining
    db_key entries from the METRICS_METADATA config value.

Idempotent: safe to re-run.  Already-prefixed keys are left as-is.
"""

import json

name = "rename_botstats_keys"
description = "Rename bigjimmy botstats keys to include bigjimmy_ prefix and strip db_key from METRICS_METADATA"

# Old key -> new key mapping
KEY_RENAMES = {
    "loop_time_seconds": "bigjimmy_loop_time_seconds",
    "loop_setup_seconds": "bigjimmy_loop_setup_seconds",
    "loop_processing_seconds": "bigjimmy_loop_processing_seconds",
    "loop_puzzle_count": "bigjimmy_loop_puzzle_count",
    "loop_avg_seconds_per_puzzle": "bigjimmy_avg_seconds_per_puzzle",
    "quota_failures": "bigjimmy_quota_failures",
    "loop_iterations_total": "bigjimmy_loop_iterations_total",
}


def run(conn):
    """Rename botstats keys and clean up METRICS_METADATA config. Returns (success, message)."""
    cursor = conn.cursor()
    renamed = 0

    # Rename botstats rows
    for old_key, new_key in KEY_RENAMES.items():
        # Only rename if the old key exists and the new key doesn't
        cursor.execute("SELECT `key` FROM botstats WHERE `key` = %s", (old_key,))
        if cursor.fetchone():
            cursor.execute("SELECT `key` FROM botstats WHERE `key` = %s", (new_key,))
            if cursor.fetchone():
                # New key already exists, just delete the old one
                cursor.execute("DELETE FROM botstats WHERE `key` = %s", (old_key,))
            else:
                cursor.execute(
                    "UPDATE botstats SET `key` = %s WHERE `key` = %s",
                    (new_key, old_key),
                )
            renamed += 1

    # Strip db_key from METRICS_METADATA config
    config_updated = False
    cursor.execute("SELECT val FROM config WHERE `key` = 'METRICS_METADATA'")
    row = cursor.fetchone()
    if row and row["val"]:
        try:
            metadata = json.loads(row["val"])
            for stat_info in metadata.values():
                if "db_key" in stat_info:
                    del stat_info["db_key"]
                    config_updated = True
            if config_updated:
                cursor.execute(
                    "UPDATE config SET val = %s WHERE `key` = 'METRICS_METADATA'",
                    (json.dumps(metadata),),
                )
        except (json.JSONDecodeError, TypeError):
            pass  # Leave malformed config alone

    conn.commit()
    parts = [f"Renamed {renamed} botstats key(s)"]
    if config_updated:
        parts.append("stripped db_key from METRICS_METADATA")
    return True, ", ".join(parts)
