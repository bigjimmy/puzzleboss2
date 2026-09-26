"""
Drop the plaintext password column from the newuser table.

Background:
    Signups used to have the person choose their real Google Workspace
    password on the Puzzleboss form, which was stored in plaintext in
    newuser.password until GET /finishaccount completed (and, for abandoned
    signups with nobody to trigger that cleanup, potentially forever).

    The account now gets a random one-time password generated at account-
    creation time (provision_new_google_user in pbgooglelib.py), emailed to
    the owner, and never persisted. Nothing reads newuser.password anymore,
    so the column -- and the liability of a real person's real password
    sitting in a database backup -- goes away.

Idempotent: safe to re-run. Skips if the column is already gone.
"""

name = "drop_newuser_password_column"
description = "Drop newuser.password now that account creation uses a one-time emailed password instead"


def run(conn):
    """Drop the password column if present. Returns (success, message)."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'newuser'
          AND COLUMN_NAME = 'password'
        """
    )
    if not cursor.fetchone():
        return True, "Column newuser.password already absent, nothing to do"

    cursor.execute("ALTER TABLE newuser DROP COLUMN password")
    conn.commit()
    return True, "Dropped newuser.password"
