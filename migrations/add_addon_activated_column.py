"""
Add addon_activated column to temp_puzzle_creation table.

Background:
    The puzzle creation flow is being expanded from 5 steps to 6, splitting
    the Google Sheet creation and Apps Script activation into separate steps.
    The addon_activated column tracks whether activation succeeded between
    steps so that step 5 (database insert) can set sheetenabled=1 on the
    puzzle row when appropriate.

Idempotent: safe to re-run. Skips if column already exists.
"""

name = "add_addon_activated_column"
description = "Add addon_activated column to temp_puzzle_creation table for 6-step creation flow"


def run(conn):
    """Add addon_activated column if it doesn't exist. Returns (success, message)."""
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute(
        """
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'temp_puzzle_creation'
          AND COLUMN_NAME = 'addon_activated'
        """
    )
    if cursor.fetchone():
        return True, "Column addon_activated already exists, nothing to do"

    cursor.execute(
        """
        ALTER TABLE temp_puzzle_creation
        ADD COLUMN `addon_activated` tinyint(1) NOT NULL DEFAULT '0'
        AFTER `drive_uri`
        """
    )
    conn.commit()
    return True, "Added addon_activated column to temp_puzzle_creation"
