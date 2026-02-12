import yaml
import sys
import inspect
import datetime
import smtplib
import MySQLdb
import MySQLdb.cursors
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


def create_db_connection():
    """Create a new MySQLdb connection using the global config.

    Returns a connection with DictCursor and utf8mb4 charset.
    This centralizes connection parameters so all consumers (bigjimmybot,
    pbrest, scripts) use identical settings.
    """
    connect_params = {
        "host": config["MYSQL"]["HOST"],
        "user": config["MYSQL"]["USERNAME"],
        "passwd": config["MYSQL"]["PASSWORD"],
        "db": config["MYSQL"]["DATABASE"],
        "cursorclass": MySQLdb.cursors.DictCursor,
        "charset": "utf8mb4",
    }
    ssl_config = get_mysql_ssl_config(config)
    if ssl_config:
        connect_params["ssl"] = ssl_config
    return MySQLdb.connect(**connect_params)


def configure_flask_mysql(app):
    """Configure a Flask app's MYSQL_* settings from the global config.

    Call this before creating a Flask-MySQLdb MySQL(app) instance.
    Centralizes config so pbrest.py doesn't duplicate connection parameters.
    """
    app.config["MYSQL_HOST"] = config["MYSQL"]["HOST"]
    app.config["MYSQL_USER"] = config["MYSQL"]["USERNAME"]
    app.config["MYSQL_PASSWORD"] = config["MYSQL"]["PASSWORD"]
    app.config["MYSQL_DB"] = config["MYSQL"]["DATABASE"]
    app.config["MYSQL_CURSORCLASS"] = "DictCursor"
    app.config["MYSQL_CHARSET"] = "utf8mb4"
    ssl_config = get_mysql_ssl_config(config)
    if ssl_config:
        app.config["MYSQL_CUSTOM_OPTIONS"] = {"ssl": ssl_config}


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
        connect_params = {
            "host": config["MYSQL"]["HOST"],
            "user": config["MYSQL"]["USERNAME"],
            "passwd": config["MYSQL"]["PASSWORD"],
            "db": config["MYSQL"]["DATABASE"],
        }
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
    round_id = int(round_id)
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
    """Assign a solver to a puzzle, unassigning from any other puzzle first.

    Solver_id is stored as INT in JSON, matching solver.id column type.
    All SQL functions use JSON_TABLE with INT PATH to extract solver_ids.
    Run the normalize_solver_ids migration after deploy to ensure consistency.
    """
    solver_id = int(solver_id)  # Normalize: 101 whether caller passes 101 or "101"
    puzzle_id = int(puzzle_id)
    debug_log(4, "Started with puzzle id %s" % puzzle_id)
    cursor = conn.cursor()

    # Find and unassign from any other puzzle the solver is currently on.
    # JSON_TABLE with INT PATH extracts solver_ids as integers for comparison.
    cursor.execute(
        """
        SELECT DISTINCT p.id FROM puzzle p,
        JSON_TABLE(
            p.current_solvers,
            '$.solvers[*]' COLUMNS (
                solver_id INT PATH '$.solver_id'
            )
        ) AS jt
        WHERE jt.solver_id = %s
    """,
        (solver_id,),
    )
    current_puzzles = cursor.fetchall()
    for current_puzzle in current_puzzles:
        if current_puzzle["id"] != puzzle_id:
            unassign_solver_from_puzzle(current_puzzle["id"], solver_id, conn)

    # Update current solvers for the new puzzle
    cursor.execute(
        "SELECT current_solvers, status FROM puzzle WHERE id = %s",
        (puzzle_id,),
    )
    row = cursor.fetchone()
    current_solvers_str = row["current_solvers"] or json.dumps(
        {"solvers": []}
    )
    current_solvers = json.loads(current_solvers_str)

    # Transition puzzle out of "New" or "Abandoned" when a solver is assigned
    if row["status"] in ("New", "Abandoned"):
        debug_log(3, "Auto-transitioning puzzle %s from '%s' to 'Being worked'" % (puzzle_id, row["status"]))
        cursor.execute(
            "UPDATE puzzle SET status = %s WHERE id = %s",
            ("Being worked", puzzle_id),
        )

    if not any(s["solver_id"] == solver_id for s in current_solvers["solvers"]):
        current_solvers["solvers"].append({"solver_id": solver_id})
        cursor.execute(
            "UPDATE puzzle SET current_solvers = %s WHERE id = %s",
            (json.dumps(current_solvers), puzzle_id),
        )

    # Update history
    cursor.execute(
        "SELECT solver_history FROM puzzle WHERE id = %s",
        (puzzle_id,),
    )
    history_str = cursor.fetchone()["solver_history"] or json.dumps({"solvers": []})
    history = json.loads(history_str)

    if not any(s["solver_id"] == solver_id for s in history["solvers"]):
        history["solvers"].append({"solver_id": solver_id})
        debug_log(5, f"Storing solver_history for puzzle {puzzle_id}: {json.dumps(history)}")
        cursor.execute(
            "UPDATE puzzle SET solver_history = %s WHERE id = %s",
            (json.dumps(history), puzzle_id),
        )

    conn.commit()


def unassign_solver_from_puzzle(puzzle_id, solver_id, conn):
    """Unassign a solver from a puzzle's current solvers list."""
    solver_id = int(solver_id)  # Normalize to int
    puzzle_id = int(puzzle_id)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT current_solvers FROM puzzle WHERE id = %s",
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
        "UPDATE puzzle SET current_solvers = %s WHERE id = %s",
        (json.dumps(current_solvers), puzzle_id),
    )

    conn.commit()


def clear_puzzle_solvers(puzzle_id, conn):
    """Clear all solvers from a puzzle's current solvers list."""
    puzzle_id = int(puzzle_id)
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


def log_activity(puzzle_id, activity_type, solver_id, source, conn, timestamp=None):
    """
    Log an activity entry to the activity table.

    Args:
        puzzle_id: Puzzle database ID
        activity_type: Type of activity ('create', 'revise', 'comment', 'interact', 'solve')
        solver_id: Solver database ID who performed the activity
        source: Source of activity ('puzzleboss', 'bigjimmybot', 'google', 'discord')
        conn: Database connection
        timestamp: Optional Unix timestamp to use instead of CURRENT_TIMESTAMP.
            When provided, the activity's `time` column is set to this value
            (via FROM_UNIXTIME). This is important for sheet-edit activity so
            the recorded time matches the actual Google Sheet edit time, not
            the server time when bigjimmybot processes it.

    Raises:
        Exception: If database insert fails
    """
    puzzle_id = int(puzzle_id)
    solver_id = int(solver_id)
    cursor = conn.cursor()
    if timestamp is not None:
        cursor.execute(
            "INSERT INTO activity (puzzle_id, solver_id, source, type, time) VALUES (%s, %s, %s, %s, FROM_UNIXTIME(%s))",
            (puzzle_id, solver_id, source, activity_type, timestamp),
        )
    else:
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


def update_puzzle_field(puzzle_id, field, value, conn, source="system"):
    """
    Update a single puzzle field in the database.

    Args:
        puzzle_id: Puzzle database ID
        field: Field name to update
        value: New value for the field
        conn: Database connection
        source: Caller identity for activity logging (default "system")

    Special handling:
        - 'solvers' field: Uses assign_solver_to_puzzle() or clear_puzzle_solvers()
        - 'status' field: Auto-logs "interact" activity (except for "Solved",
          which is logged as "solve" by the answer handler in pbrest.py)
        - Other fields: Direct UPDATE query

    Raises:
        Exception: If database update fails
    """
    puzzle_id = int(puzzle_id)
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

        # Invariant: all non-Solved status changes are logged as "interact" activity.
        # "Solved" is excluded because solves are logged as "solve" type via the
        # answer handler — logging "interact" here would duplicate it.
        if field == "status" and value != "Solved":
            log_activity(puzzle_id, "interact", 0, source, conn)


def get_solver_by_id_from_db(solver_id, conn):
    """Get solver by ID from database, including last activity.

    Args:
        solver_id: Solver database ID
        conn: Database connection

    Returns:
        Solver dict from solver_view with 'lastact' key added, or None if not found.
    """
    solver_id = int(solver_id)
    cursor = conn.cursor()
    cursor.execute("SELECT * from solver_view where id = %s", (solver_id,))
    solver = cursor.fetchone()
    if solver is None:
        return None
    solver["lastact"] = get_last_activity_for_solver(solver_id, conn)
    return solver


def get_last_activity_for_solver(solver_id, conn):
    """Get the most recent activity record for a solver.

    Args:
        solver_id: Solver database ID
        conn: Database connection

    Returns:
        Activity dict with 'time' as datetime object, or None if no activity.
    """
    solver_id = int(solver_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * from activity where solver_id = %s ORDER BY time DESC LIMIT 1",
        (solver_id,),
    )
    return cursor.fetchone()


def get_last_sheet_activity_for_puzzle(puzzle_id, conn):
    """Get the last 'revise' type activity for a puzzle (sheet edits only).

    Args:
        puzzle_id: Puzzle database ID
        conn: Database connection

    Returns:
        Activity dict with 'time' as datetime object, or None if no activity.
    """
    puzzle_id = int(puzzle_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * from activity where puzzle_id = %s AND type = 'revise' ORDER BY time DESC LIMIT 1",
        (puzzle_id,),
    )
    return cursor.fetchone()


def get_last_activity_for_puzzle(puzzle_id, conn):
    """Get the most recent activity record for a puzzle (any type).

    Args:
        puzzle_id: Puzzle database ID
        conn: Database connection

    Returns:
        Activity dict with 'time' as datetime object, or None if no activity.
    """
    puzzle_id = int(puzzle_id)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * from activity where puzzle_id = %s ORDER BY time DESC LIMIT 1",
        (puzzle_id,),
    )
    return cursor.fetchone()


def update_botstat(key, value, conn):
    """Insert or update a bot statistic.

    Args:
        key: Stat key name
        value: Stat value (string)
        conn: Database connection
    """
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO botstats (`key`, `val`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `val`=%s",
        (key, value, value),
    )
    conn.commit()


def get_all_rounds_with_puzzles(conn):
    """Fetch all rounds with their nested puzzles from database.

    Args:
        conn: Database connection

    Returns:
        List of round dicts, each with a 'puzzles' key containing list of puzzle dicts.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT * from puzzle_view")
    puzzle_view = cursor.fetchall()

    all_puzzles = {}
    for puzzle in puzzle_view:
        all_puzzles[puzzle["id"]] = puzzle

    cursor.execute("SELECT * from round_view")
    round_view = cursor.fetchall()

    def is_int(val):
        try:
            int(val)
            return True
        except Exception:
            return False

    rounds = []
    for rnd in round_view:
        if "puzzles" in rnd and rnd["puzzles"]:
            rnd["puzzles"] = [
                all_puzzles[int(pid)]
                for pid in rnd["puzzles"].split(",")
                if is_int(pid) and int(pid) in all_puzzles
            ]
        else:
            rnd["puzzles"] = []
        rounds.append(rnd)

    return rounds
