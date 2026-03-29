"""
Add SERVICE_ACCOUNT_JSON config key to existing databases.

Background:
    Service account credentials are now stored in the config table as
    SERVICE_ACCOUNT_JSON (the full JSON key file contents) rather than
    as a file path in SERVICE_ACCOUNT_FILE.  This removes the need to
    provision the key file on the server filesystem.

    pbgooglelib.py now prefers SERVICE_ACCOUNT_JSON and falls back to
    reading SERVICE_ACCOUNT_FILE from disk if the JSON key is not set.

Idempotent: safe to re-run.  Skips if SERVICE_ACCOUNT_JSON already exists.
"""

name = "add_service_account_json_config"
description = "Add SERVICE_ACCOUNT_JSON config key for storing service account credentials in the database"


def run(conn):
    """Insert SERVICE_ACCOUNT_JSON row if it doesn't already exist."""
    cursor = conn.cursor()

    cursor.execute(
        "SELECT `key` FROM config WHERE `key` = 'SERVICE_ACCOUNT_JSON'"
    )
    if cursor.fetchone():
        return True, "SERVICE_ACCOUNT_JSON config key already exists, nothing to do"

    cursor.execute(
        "INSERT INTO config (`key`, val) VALUES ('SERVICE_ACCOUNT_JSON', '')"
    )
    conn.commit()
    return True, "Added SERVICE_ACCOUNT_JSON config key"
