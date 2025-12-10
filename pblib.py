import yaml
import sys
import inspect
import datetime
import bleach
import smtplib
import MySQLdb
from flask import Flask, request
from flask_restful import Api
from flask_mysqldb import MySQL
from email.message import EmailMessage

# Global config variable for YAML config
config = None
huntfolderid = "undefined"

# Pre-initialize configstruct with default LOGLEVEL
configstruct = {"LOGLEVEL": "4"}

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
    """Reload configuration from both YAML file and database"""
    global configstruct, config
    
    # Reload YAML config
    try:
        with open("puzzleboss.yaml") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
        debug_log(3, "YAML configuration reloaded")
    except Exception as e:
        debug_log(0, f"FATAL EXCEPTION reading YAML configuration: {e}")
        sys.exit(255)

    # Reload database config
    try:
        db_connection = MySQLdb.connect(config["MYSQL"]["HOST"], config["MYSQL"]["USERNAME"], config["MYSQL"]["PASSWORD"], config["MYSQL"]["DATABASE"])
        cursor = db_connection.cursor()
        cursor.execute("SELECT * FROM config")
        configdump = cursor.fetchall()
        db_connection.close()
        configstruct.clear()
        configstruct.update(dict(configdump))
        debug_log(3, "Database configuration reloaded")
    except Exception as e:
        debug_log(0, f"FATAL EXCEPTION reading database configuration: {e}")
        sys.exit(255)

# Initial configuration load
refresh_config()

def sanitize_string(mystring):
    import re
    if mystring is None:
        return ""
    # Keep alphanumeric, emoji, spaces, and common punctuation
    # But remove control chars and problematic URL/filename chars
    sanitized = re.sub(r'[\x00-\x1F\x7F<>:"\\|?*]', '', mystring)
    # Trim whitespace
    return sanitized.strip()

def sanitize_puzzle_name(mystring):
    import re
    if mystring is None:
        return ""
    # Keep alphanumeric, emoji, and common punctuation
    # Remove spaces and problematic URL/filename chars
    sanitized = re.sub(r'[\x00-\x1F\x7F<>:"\\|?* ]', '', mystring)
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
