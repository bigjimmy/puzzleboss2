import yaml
import sys
import inspect
import datetime
import smtplib
import MySQLdb
from email.message import EmailMessage

# Global config variable for YAML config
config = None
huntfolderid = "undefined"

# Pre-initialize configstruct with default LOGLEVEL
configstruct = {"LOGLEVEL": "4"}

# Track last config refresh time for periodic refresh
_last_config_refresh = None
CONFIG_REFRESH_INTERVAL = 30  # seconds


def maybe_refresh_config():
    """Refresh config if enough time has passed since last refresh.
    Call this periodically (e.g., on each request) to ensure config stays current.
    """
    global _last_config_refresh
    import time

    now = time.time()
    if (
        _last_config_refresh is None
        or (now - _last_config_refresh) >= CONFIG_REFRESH_INTERVAL
    ):
        try:
            refresh_config()
            _last_config_refresh = now
        except Exception as e:
            # Don't crash on refresh failure, just log it
            print(f"[WARNING] Config refresh failed: {e}", flush=True)


def debug_log(sev, message):
    # Levels:
    # 0 = emergency
    # 1 = error
    # 2 = warning
    # 3 = info
    # 4 = debug
    # 5 = trace

    if int(configstruct["LOGLEVEL"]) >= sev:
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        print(
            "[%s] [SEV%s] %s: %s"
            % (timestamp, sev, inspect.currentframe().f_back.f_code.co_name, message),
            flush=True,
        )
    return


def refresh_config():
    """Reload configuration from both YAML file and database.
    Only updates and logs if there are actual changes.
    """
    global configstruct, config, _last_config_refresh
    import time

    # Reload YAML config (rarely changes at runtime, so no comparison)
    try:
        with open("puzzleboss.yaml") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
    except Exception as e:
        debug_log(0, f"FATAL EXCEPTION reading YAML configuration: {e}")
        sys.exit(255)

    # Reload database config with change detection
    try:
        db_connection = MySQLdb.connect(
            config["MYSQL"]["HOST"],
            config["MYSQL"]["USERNAME"],
            config["MYSQL"]["PASSWORD"],
            config["MYSQL"]["DATABASE"],
        )
        cursor = db_connection.cursor()
        cursor.execute("SELECT * FROM config")
        configdump = cursor.fetchall()
        db_connection.close()

        new_config = dict(configdump)
        _last_config_refresh = time.time()  # Update timestamp

        # Check if this is initial load (only default LOGLEVEL present)
        is_initial_load = len(configstruct) <= 1 and "LOGLEVEL" in configstruct

        if is_initial_load:
            # Initial load - just set config, no comparison
            configstruct.clear()
            configstruct.update(new_config)
            debug_log(3, "Initial configuration loaded")
        else:
            # Compare and detect changes
            changes_found = False

            # Check for modified or new keys
            for key, value in new_config.items():
                old_value = configstruct.get(key)
                if old_value != value:
                    if old_value is None:
                        debug_log(3, f"Config added: {key} = {value}")
                    else:
                        debug_log(3, f"Config changed: {key}: {old_value} -> {value}")
                    changes_found = True

            # Check for removed keys
            for key in configstruct:
                if key not in new_config:
                    debug_log(3, f"Config removed: {key}")
                    changes_found = True

            # Only update if there were changes
            if changes_found:
                configstruct.clear()
                configstruct.update(new_config)
                debug_log(3, "Configuration updated with changes")
            else:
                debug_log(5, "Configuration checked, no changes detected")

    except Exception as e:
        debug_log(0, f"FATAL EXCEPTION reading database configuration: {e}")
        sys.exit(255)


# Initial configuration load
refresh_config()


def sanitize_puzzle_name(mystring):
    import re

    if mystring is None:
        return ""
    # Keep alphanumeric, emoji, and common punctuation
    # Remove spaces and problematic URL/filename chars
    sanitized = re.sub(r'[\x00-\x1F\x7F<>:"\\|?* ]', "", mystring)
    # Trim whitespace
    return sanitized.strip()


def email_user_verification(email, code, fullname, username):
    debug_log(4, "start for email: %s" % email)

    verification_url = "%s/index.php?code=%s" % (configstruct["ACCT_URI"], code)
    team_name = configstruct["TEAMNAME"]

    messagecontent = """Hi %s,

Welcome to %s! To complete your account setup, please visit the link below:

%s

Account details:
- Username: %s
- Display name: %s

This link will finish creating your account so you can access our puzzle-solving tools.

If you did not request this account, you can safely ignore this email.

Thanks,
The %s Puzzletech Team

---
This is an automated message from %s registration system.
""" % (
        fullname,
        team_name,
        verification_url,
        username,
        fullname,
        team_name,
        team_name,
    )

    debug_log(4, "Email to be sent: %s" % messagecontent)

    try:
        msg = EmailMessage()
        msg["Subject"] = "%s - Complete your account registration" % team_name
        msg["From"] = "%s" % configstruct["REGEMAIL"]
        msg["To"] = email
        msg.set_content(messagecontent)
        s = smtplib.SMTP(configstruct["MAILRELAY"])
        s.send_message(msg)
        s.quit()

    except Exception as e:
        errmsg = str(e)
        debug_log(2, "Exception sending email: %s" % errmsg)
        return errmsg

    return "OK"
