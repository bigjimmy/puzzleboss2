import yaml
import sys
import inspect
import datetime
import smtplib
import MySQLdb
import json
from email.message import EmailMessage

# Global config variable for YAML config
config = None
huntfolderid = "undefined"

# Pre-initialize configstruct with default LOGLEVEL
configstruct = {"LOGLEVEL": "4"}

# Track last config refresh time for periodic refresh
_last_config_refresh = None
CONFIG_REFRESH_INTERVAL = 30  # seconds


def get_mysql_ssl_config(config):
    """Extract SSL configuration from config dict for MySQL connections.

    Returns a dict suitable for MySQLdb ssl parameter, or None if SSL not configured.
    Supports optional client certificates for mutual TLS.
    """
    if "SSL" not in config.get("MYSQL", {}) or "CA" not in config["MYSQL"]["SSL"]:
        return None

    ssl_config = {"ca": config["MYSQL"]["SSL"]["CA"]}

    # Optional: Client certificate for mutual TLS (rarely needed)
    if "CERT" in config["MYSQL"]["SSL"]:
        ssl_config["cert"] = config["MYSQL"]["SSL"]["CERT"]
    if "KEY" in config["MYSQL"]["SSL"]:
        ssl_config["key"] = config["MYSQL"]["SSL"]["KEY"]

    return ssl_config


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
        # Build connection parameters
        connect_params = {
            "host": config["MYSQL"]["HOST"],
            "user": config["MYSQL"]["USERNAME"],
            "passwd": config["MYSQL"]["PASSWORD"],
            "db": config["MYSQL"]["DATABASE"],
        }

        # Add SSL configuration if present
        ssl_config = get_mysql_ssl_config(config)
        if ssl_config:
            connect_params["ssl"] = ssl_config

        db_connection = MySQLdb.connect(**connect_params)
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
                        display_val = value if len(str(value)) <= 80 else f"{str(value)[:77]}..."
                        debug_log(3, f"Config added: {key} = {display_val}")
                    else:
                        display_old = str(old_value) if len(str(old_value)) <= 40 else f"{str(old_value)[:37]}..."
                        display_new = str(value) if len(str(value)) <= 40 else f"{str(value)[:37]}..."
                        debug_log(3, f"Config changed: {key}: {display_old} -> {display_new}")
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

    verification_url = f"{configstruct['ACCT_URI']}/index.php?code={code}"
    team_name = configstruct["TEAMNAME"]

    messagecontent = f"""Hi {fullname},

Welcome to {team_name}! To complete your account setup, please visit the link below:

{verification_url}

Account details:
- Username: {username}
- Display name: {fullname}

This link will finish creating your account so you can access our puzzle-solving tools.

If you did not request this account, you can safely ignore this email.

Thanks,
The {team_name} Puzzletech Team

---
This is an automated message from {team_name} registration system.
"""

    debug_log(4, "Email to be sent: %s" % messagecontent)

    try:
        msg = EmailMessage()
        msg["Subject"] = f"{team_name} - Complete your account registration"
        msg["From"] = configstruct["REGEMAIL"]
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


# Business logic functions for solver assignment and round completion

def check_round_completion(round_id, conn):
    """Check if all meta puzzles in a round are solved and update round status accordingly."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) as total, SUM(CASE WHEN status = 'Solved' THEN 1 ELSE 0 END) as solved
            FROM puzzle
            WHERE round_id = %s AND ismeta = 1
            """,
            (round_id,),
        )
        result = cursor.fetchone()
        if result["total"] > 0 and result["total"] == result["solved"]:
            # All meta puzzles are solved, mark the round as solved
            cursor.execute(
                "UPDATE round SET status = 'Solved' WHERE id = %s", (round_id,)
            )
            conn.commit()
            debug_log(
                3, "Round %s marked as solved - all meta puzzles completed" % round_id
            )
        elif result["total"] > 0 and result["total"] != result["solved"]:
            # Not all meta puzzles are solved, ensure round is not marked as solved
            cursor.execute(
                "UPDATE round SET status = 'New' WHERE id = %s AND status = 'Solved'", (round_id,)
            )
            if cursor.rowcount > 0:
                conn.commit()
                debug_log(
                    3, "Round %s unmarked as solved - not all meta puzzles completed" % round_id
                )
    except Exception:
        debug_log(1, "Error checking round completion status for round %s" % round_id)


def assign_solver_to_puzzle(puzzle_id, solver_id, conn):
    """Assign a solver to a puzzle, unassigning from any other puzzle first."""
    debug_log(4, "Started with puzzle id %s" % puzzle_id)
    cursor = conn.cursor()

    # First, find and unassign from any other puzzle the solver is currently working on
    cursor.execute(
        """
        SELECT id FROM puzzle
        WHERE JSON_CONTAINS(current_solvers,
            JSON_OBJECT('solver_id', %s),
            '$.solvers'
        )
    """,
        (solver_id,),
    )
    current_puzzle = cursor.fetchone()
    if current_puzzle and current_puzzle["id"] != puzzle_id:
        # Unassign from current puzzle if it's different from the new one
        unassign_solver_from_puzzle(current_puzzle["id"], solver_id, conn)

    # Update current solvers for the new puzzle
    cursor.execute(
        """
        SELECT current_solvers FROM puzzle WHERE id = %s
    """,
        (puzzle_id,),
    )
    current_solvers_str = cursor.fetchone()["current_solvers"] or json.dumps(
        {"solvers": []}
    )
    current_solvers = json.loads(current_solvers_str)

    # Add new solver if not already present
    if not any(s["solver_id"] == solver_id for s in current_solvers["solvers"]):
        current_solvers["solvers"].append({"solver_id": solver_id})
        cursor.execute(
            """
            UPDATE puzzle
            SET current_solvers = %s
            WHERE id = %s
        """,
            (json.dumps(current_solvers), puzzle_id),
        )

    # Update history
    cursor.execute(
        """
        SELECT solver_history FROM puzzle WHERE id = %s
    """,
        (puzzle_id,),
    )
    history_str = cursor.fetchone()["solver_history"] or json.dumps({"solvers": []})
    history = json.loads(history_str)

    # Add to history if not already present
    # Normalize to int for storage, but check against both int and string for legacy data
    solver_id_int = int(solver_id)
    existing_ids = [s["solver_id"] for s in history["solvers"]]
    # Check if already present as either int or string
    if not any(sid == solver_id_int or str(sid) == str(solver_id_int) for sid in existing_ids):
        history["solvers"].append({"solver_id": solver_id_int})
        history_json = json.dumps(history)
        debug_log(5, f"Storing solver_history for puzzle {puzzle_id}: {history_json}, solver_id_int type: {type(solver_id_int)}")
        cursor.execute(
            """
            UPDATE puzzle
            SET solver_history = %s
            WHERE id = %s
        """,
            (history_json, puzzle_id),
        )

    conn.commit()


def unassign_solver_from_puzzle(puzzle_id, solver_id, conn):
    """Unassign a solver from a puzzle's current solvers list."""
    cursor = conn.cursor()

    # Update current solvers
    cursor.execute(
        """
        SELECT current_solvers FROM puzzle WHERE id = %s
    """,
        (puzzle_id,),
    )
    current_solvers_str = cursor.fetchone()["current_solvers"] or json.dumps(
        {"solvers": []}
    )
    current_solvers = json.loads(current_solvers_str)

    current_solvers["solvers"] = [
        s for s in current_solvers["solvers"] if s["solver_id"] != solver_id
    ]

    cursor.execute(
        """
        UPDATE puzzle
        SET current_solvers = %s
        WHERE id = %s
    """,
        (json.dumps(current_solvers), puzzle_id),
    )

    conn.commit()


def clear_puzzle_solvers(puzzle_id, conn):
    """Clear all solvers from a puzzle's current solvers list."""
    cursor = conn.cursor()

    # Clear current solvers
    cursor.execute(
        """
        UPDATE puzzle
        SET current_solvers = '{"solvers": []}'
        WHERE id = %s
    """,
        (puzzle_id,),
    )

    conn.commit()


def log_activity(puzzle_id, activity_type, solver_id, source, conn):
    """
    Log an activity entry to the activity table.

    Args:
        puzzle_id: Puzzle database ID
        activity_type: Type of activity ('create', 'revise', 'comment', 'interact', 'solve')
        solver_id: Solver database ID who performed the activity
        source: Source of activity ('puzzleboss', 'bigjimmybot', 'google', 'discord')
        conn: Database connection

    Raises:
        Exception: If database insert fails
    """
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO activity (puzzle_id, solver_id, source, type) VALUES (%s, %s, %s, %s)",
        (puzzle_id, solver_id, source, activity_type),
    )
    conn.commit()


def get_solver_by_name_from_db(name, conn):
    """
    Get solver by username from database.

    Args:
        name: Solver username
        conn: Database connection

    Returns:
        Solver dict from solver_view if found, None if not found

    Raises:
        Exception: If database query fails
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * from solver_view where name = %s", (name,))
    return cursor.fetchone()


def solver_exists(identifier, conn):
    """
    Check if a solver exists in the database.

    Args:
        identifier: Either solver ID (int) or username (str)
        conn: Database connection

    Returns:
        True if solver exists, False otherwise
    """
    try:
        cursor = conn.cursor()

        # Check by id if integer, by name if string
        if isinstance(identifier, int):
            cursor.execute("SELECT id FROM solver WHERE id = %s", (identifier,))
        else:
            cursor.execute("SELECT id FROM solver WHERE name = %s", (identifier,))

        solver = cursor.fetchone()
        return solver is not None
    except Exception:
        return False


def update_puzzle_field(puzzle_id, field, value, conn):
    """
    Update a single puzzle field in the database.

    Args:
        puzzle_id: Puzzle database ID
        field: Field name to update
        value: New value for the field
        conn: Database connection

    Special handling:
        - 'solvers' field: Uses assign_solver_to_puzzle() or clear_puzzle_solvers()
        - Other fields: Direct UPDATE query

    Raises:
        Exception: If database update fails
    """
    if field == "solvers":
        # Handle solver assignments using existing functions
        if value:  # Assign solver
            assign_solver_to_puzzle(puzzle_id, value, conn)
        else:  # Clear all solvers
            clear_puzzle_solvers(puzzle_id, conn)
    else:
        # Handle other puzzle updates
        cursor = conn.cursor()
        cursor.execute(f"UPDATE puzzle SET {field} = %s WHERE id = %s", (value, puzzle_id))
        conn.commit()
