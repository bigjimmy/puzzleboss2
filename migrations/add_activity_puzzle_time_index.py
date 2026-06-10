"""
Add composite index (puzzle_id, time) to the activity table.

Background:
    The two hottest activity queries can't use the existing single-column
    indexes efficiently:

    1. The lastactcached GROUP BY in /all rebuilds (pbrest._get_all_from_db)
       scans every activity row to find each puzzle's MAX(time). With the
       composite index it becomes a loose index scan over ~one entry per
       puzzle: measured 240ms -> 1.1ms at 400K rows, and cost stays flat
       as activity grows.

    2. get_last_activity_for_puzzle's WHERE puzzle_id=? ORDER BY time DESC
       LIMIT 1 bait's the optimizer into a backward scan of the `time`
       index, which degrades badly for puzzles whose last activity is old
       (measured 184ms at 400K rows; 0.1ms with the composite index).

    See REDIS_MIGRATION.md "Phase A" for the full measurements.

Idempotent: safe to re-run. Skips if the index already exists.
"""

name = "add_activity_puzzle_time_index"
description = "Add composite index (puzzle_id, time) to activity for lastact query performance"


def run(conn):
    """Add idx_puzzle_time index if it doesn't exist. Returns (success, message)."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'activity'
          AND INDEX_NAME = 'idx_puzzle_time'
        """
    )
    if cursor.fetchone():
        return True, "Index idx_puzzle_time already exists, nothing to do"

    # Online DDL: INPLACE with no table copy on MySQL 8; does not block reads/writes.
    cursor.execute(
        "ALTER TABLE activity ADD INDEX idx_puzzle_time (puzzle_id, time)"
    )
    conn.commit()
    return True, "Added idx_puzzle_time (puzzle_id, time) index to activity"
