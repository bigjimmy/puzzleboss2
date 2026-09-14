"""
Add composite index (solver_id, time) to the activity table.

Background:
    get_last_activity_for_solver's WHERE solver_id=? ORDER BY time DESC
    LIMIT 1 (run for every editor record bigjimmybot processes, and for
    /solvers/<id> lookups) has the same shape as the puzzle-side query fixed
    by add_activity_puzzle_time_index: the single-column indexes bait the
    optimizer into either a full scan of the solver's rows or a backward
    scan of the `time` index, degrading as activity grows during a hunt.
    The composite index makes it a single index seek.

Idempotent: safe to re-run. Skips if the index already exists.
"""

name = "add_activity_solver_time_index"
description = "Add composite index (solver_id, time) to activity for last-solver-activity query performance"


def run(conn):
    """Add idx_solver_time index if it doesn't exist. Returns (success, message)."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT INDEX_NAME FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'activity'
          AND INDEX_NAME = 'idx_solver_time'
        """
    )
    if cursor.fetchone():
        return True, "Index idx_solver_time already exists, nothing to do"

    # Online DDL: INPLACE with no table copy on MySQL 8; does not block reads/writes.
    cursor.execute(
        "ALTER TABLE activity ADD INDEX idx_solver_time (solver_id, time)"
    )
    conn.commit()
    return True, "Added idx_solver_time (solver_id, time) index to activity"
