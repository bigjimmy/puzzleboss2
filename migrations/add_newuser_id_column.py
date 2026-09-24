"""
Add a non-secret auto-increment id to the newuser table, and stop treating
the verification code as its primary key.

Background:
    GET /newusers (the admin pending-registrations list) used to return the
    verification `code` for every row so the admin UI had something to key
    off of for deletion. But `code` is also the bearer credential that
    GET /finishaccount/<code> uses to actually create the account -- anyone
    who could read /newusers could see it and complete (or hijack) someone
    else's in-flight signup. The fix is for the admin list/delete flow to
    use a non-secret identifier instead, which needs one to exist.

    `code` remains UNIQUE (finish_account's WHERE code = %s still needs a
    fast, correct lookup); `id` becomes the primary key and is what the
    admin API/UI reference from here on.

Idempotent: safe to re-run. Skips if the `id` column already exists.
"""

name = "add_newuser_id_column"
description = "Add auto-increment id to newuser; code becomes a unique key instead of the primary key"


def run(conn):
    """Add id column/PK swap if not already done. Returns (success, message)."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'newuser'
          AND COLUMN_NAME = 'id'
        """
    )
    if cursor.fetchone():
        return True, "Column newuser.id already exists, nothing to do"

    cursor.execute(
        """
        ALTER TABLE newuser
          ADD COLUMN id INT NOT NULL AUTO_INCREMENT FIRST,
          DROP PRIMARY KEY,
          ADD PRIMARY KEY (id),
          ADD UNIQUE KEY code_UNIQUE (code)
        """
    )
    conn.commit()
    return True, "Added newuser.id (primary key); code is now a unique key"
