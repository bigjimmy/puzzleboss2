"""
Add the `secret` flag column to the config table and backfill it.

Background:
    Config secrets are redacted in GET /config and GET /huntinfo responses
    unless the caller presents the internal token. Secrecy classification is
    "flag as authority, heuristic as fallback": the `config.secret` column is
    the authoritative per-key flag, with pblib.is_secret_config_key's
    name-pattern heuristic (API_KEY/SECRET/PASSWORD/TOKEN/WEBHOOK +
    SERVICE_ACCOUNT_JSON) retained as a safety net for keys that were never
    flagged. A key is redacted if EITHER says so.

    The backfill flags:
    - every existing key the heuristic classifies as secret (making today's
      implicit classification explicit and auditable), plus
    - known legacy secrets whose names the heuristic misses and which may
      linger in older databases with real credentials: LDAP_ADMINPW,
      SHEETS_ADDON_COOKIES, SHEETS_ADDON_REFRESH_HEADERS,
      SHEETS_ADDON_INVOKE_PARAMS.

Idempotent: safe to re-run. Skips the ALTER if the column already exists;
the backfill UPDATE only promotes 0 -> 1 (never unflags an operator's
explicit choice).
"""

from pblib import is_secret_config_key

name = "add_config_secret_flag"
description = "Add config.secret flag column and backfill from the secret-name heuristic"

# Legacy keys that held credentials but don't match the name heuristic.
# Deprecated (hidden in the config UI) yet may persist in older databases.
LEGACY_SECRET_KEYS = (
    "LDAP_ADMINPW",
    "SHEETS_ADDON_COOKIES",
    "SHEETS_ADDON_REFRESH_HEADERS",
    "SHEETS_ADDON_INVOKE_PARAMS",
)


def run(conn):
    """Add config.secret column and backfill flags. Returns (success, message)."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'config'
          AND COLUMN_NAME = 'secret'
        """
    )
    column_existed = cursor.fetchone() is not None

    if not column_existed:
        cursor.execute(
            "ALTER TABLE config ADD COLUMN `secret` tinyint(1) NOT NULL DEFAULT 0"
        )

    # Backfill: heuristic-matched keys + explicit legacy list. Promote-only
    # (0 -> 1) so a re-run never clobbers operator decisions.
    # (Rows may be tuples or dicts — the API's migrate endpoint hands us a
    # DictCursor connection, direct scripts a plain one.)
    cursor.execute("SELECT `key` FROM config WHERE `secret` = 0")
    unflagged = [
        row["key"] if isinstance(row, dict) else row[0]
        for row in cursor.fetchall()
    ]
    to_flag = [
        key
        for key in unflagged
        if is_secret_config_key(key) or key in LEGACY_SECRET_KEYS
    ]
    if to_flag:
        placeholders = ", ".join(["%s"] * len(to_flag))
        cursor.execute(
            f"UPDATE config SET `secret` = 1 WHERE `key` IN ({placeholders})",
            to_flag,
        )

    conn.commit()

    column_msg = (
        "column already existed" if column_existed else "added `secret` column"
    )
    return True, (
        f"config.secret: {column_msg}; flagged {len(to_flag)} key(s) "
        f"({', '.join(sorted(to_flag)) if to_flag else 'none needed'})"
    )
