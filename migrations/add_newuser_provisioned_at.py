"""
Add newuser.provisioned_at: when GET /finishaccount last created or reissued
the Google Workspace account for this signup code.

pbrest._claim_provisioning_slot does an atomic conditional UPDATE on this
column so that concurrent or repeated step-2 calls for one code (double
click, two tabs, or a leaked code) don't each reissue a fresh one-time
password and send another email.

Idempotent: safe to re-run.
"""

name = "add_newuser_provisioned_at"
description = "Add newuser.provisioned_at for the one-time-password reissue cooldown"


def run(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'newuser'
          AND COLUMN_NAME = 'provisioned_at'
        """
    )
    if cursor.fetchone():
        return True, "Column newuser.provisioned_at already present, nothing to do"

    cursor.execute("ALTER TABLE newuser ADD COLUMN provisioned_at DATETIME NULL DEFAULT NULL")
    conn.commit()
    return True, "Added newuser.provisioned_at"
