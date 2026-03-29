"""
Add RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY config keys.

Background:
    The account signup page (account/index.php) now supports Google reCAPTCHA
    v3 on the gate login form and the registration form.  Both keys are stored
    in the config table so they can be managed via the admin config UI without
    a deployment.

    Set RECAPTCHA_SITE_KEY to the public site key and RECAPTCHA_SECRET_KEY to
    the server-side secret key.  Leave both empty to disable CAPTCHA (dev mode).

Idempotent: safe to re-run.
"""

name = "add_recaptcha_config"
description = "Add RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY config keys for account signup CAPTCHA"


def run(conn):
    cursor = conn.cursor()
    inserted = []

    for key in ("RECAPTCHA_SITE_KEY", "RECAPTCHA_SECRET_KEY"):
        cursor.execute("SELECT `key` FROM config WHERE `key` = %s", (key,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO config (`key`, val) VALUES (%s, '')", (key,))
            inserted.append(key)

    if inserted:
        conn.commit()
        return True, f"Added config keys: {', '.join(inserted)}"
    return True, "RECAPTCHA config keys already exist, nothing to do"
