import MySQLdb
import sys
import flasgger
import pblib
import traceback
import json
import os
from flask import Flask, request
from flask_restful import Api
from flask_mysqldb import MySQL
from pblib import *
import pbgooglelib
from pbgooglelib import *
from pbdiscordlib import *
from secrets import token_hex
from flasgger.utils import swag_from
from werkzeug.exceptions import HTTPException

# Prometheus multiprocess setup - must be done BEFORE importing prometheus
# This allows metrics to be aggregated across Gunicorn workers
PROMETHEUS_MULTIPROC_DIR = os.environ.get("prometheus_multiproc_dir")
if not PROMETHEUS_MULTIPROC_DIR:
    # Use /dev/shm (RAM-backed) if available, otherwise /tmp
    if os.path.exists("/dev/shm"):
        PROMETHEUS_MULTIPROC_DIR = "/dev/shm/puzzleboss_prometheus"
    else:
        PROMETHEUS_MULTIPROC_DIR = "/tmp/puzzleboss_prometheus"
    os.environ["prometheus_multiproc_dir"] = PROMETHEUS_MULTIPROC_DIR

# Create the directory if it doesn't exist
if not os.path.exists(PROMETHEUS_MULTIPROC_DIR):
    try:
        os.makedirs(PROMETHEUS_MULTIPROC_DIR, exist_ok=True)
        debug_log(3, f"Created prometheus multiproc dir: {PROMETHEUS_MULTIPROC_DIR}")
    except Exception as e:
        debug_log(2, f"Failed to create prometheus multiproc dir: {e}")

# Prometheus metrics - multiprocess mode is enabled via prometheus_multiproc_dir env var
PROMETHEUS_AVAILABLE = False
try:
    from prometheus_flask_exporter import PrometheusMetrics

    PROMETHEUS_AVAILABLE = True
    debug_log(
        3,
        f"prometheus_flask_exporter available (multiproc_dir: {PROMETHEUS_MULTIPROC_DIR})",
    )
except ImportError:
    debug_log(
        3, "prometheus_flask_exporter not installed - /metrics endpoint unavailable"
    )

# LLM query support (via pbllmlib)
from pbllmlib import GEMINI_AVAILABLE, process_query as llm_process_query

# Cache support (via pbcachelib)
from pbcachelib import (
    init_memcache,
    cache_get,
    cache_set,
    cache_delete,
    invalidate_all_cache,
    increment_cache_stat,
    ensure_memcache_initialized,
    MEMCACHE_CACHE_KEY,
    MEMCACHE_TTL,
)
import pbcachelib

app = Flask(__name__)
app.url_map.strict_slashes = False  # Allow trailing slashes on all routes
app.config["MYSQL_HOST"] = config["MYSQL"]["HOST"]
app.config["MYSQL_USER"] = config["MYSQL"]["USERNAME"]
app.config["MYSQL_PASSWORD"] = config["MYSQL"]["PASSWORD"]
app.config["MYSQL_DB"] = config["MYSQL"]["DATABASE"]
app.config["MYSQL_CURSORCLASS"] = "DictCursor"
app.config["MYSQL_CHARSET"] = "utf8mb4"

# SSL configuration (optional)
ssl_config = get_mysql_ssl_config(config)
if ssl_config:
    app.config["MYSQL_CUSTOM_OPTIONS"] = {"ssl": ssl_config}
    debug_log(3, f"MySQL SSL enabled with CA: {ssl_config['ca']}")

mysql = MySQL(app)
api = Api(app)
swagger = flasgger.Swagger(app)

# Initialize Prometheus metrics (exposes /metrics endpoint)
# Multiprocess aggregation is handled by prometheus_client when prometheus_multiproc_dir is set
if PROMETHEUS_AVAILABLE:
    try:
        debug_log(3, "Initializing PrometheusMetrics...")
        metrics = PrometheusMetrics(app, group_by_endpoint=True)
        # group_by_endpoint=True uses route templates like /puzzles/<id>
        # instead of actual paths like /puzzles/1, /puzzles/2, etc.
        # This reduces metric cardinality significantly.

        # Add app info label
        metrics.info("puzzleboss_api", "Puzzleboss REST API", version="1.0")
        debug_log(3, "PrometheusMetrics initialized successfully")
    except Exception as e:
        debug_log(0, f"Failed to initialize Prometheus metrics: {e}")
        PROMETHEUS_AVAILABLE = False

# Helper to invalidate cache with optional stats tracking
def invalidate_cache_with_stats():
    """Invalidate cache and track stats (with error handling for stats)."""
    invalidate_all_cache(mysql.connection)
    try:
        increment_cache_stat("cache_invalidations_total", mysql.connection)
    except Exception as e:
        debug_log(3, f"Failed to increment cache stats: {e}")


# ── Internal helpers ──────────────────────────────────────────────────────

def _cursor():
    """Get a DB connection and cursor."""
    conn = mysql.connection
    return conn, conn.cursor()


def _read_cursor():
    """Get a DB cursor with READ UNCOMMITTED for read-only queries."""
    conn, cursor = _cursor()
    cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
    return conn, cursor


def _log_activity(puzzle_id, activity_type, solver_id=100, source="puzzleboss"):
    """Log an activity entry. Fails silently (logs error only)."""
    try:
        conn, cursor = _cursor()
        cursor.execute(
            "INSERT INTO activity (puzzle_id, solver_id, source, type) VALUES (%s, %s, %s, %s)",
            (puzzle_id, solver_id, source, activity_type),
        )
        conn.commit()
    except Exception as e:
        debug_log(1, "Failed to log activity for puzzle %s: %s" % (puzzle_id, e))


def _get_status_names():
    """Get puzzle status names from the DB ENUM definition."""
    conn, cursor = _read_cursor()
    cursor.execute("SHOW COLUMNS FROM puzzle WHERE Field = 'status'")
    row = cursor.fetchone()
    if not row or not row.get("Type", "").startswith("enum("):
        return []
    return [v.strip("'") for v in row["Type"][5:-1].split("','")]


# Periodic config refresh on each request (checks if 60s have passed)
@app.before_request
def periodic_config_refresh():
    maybe_refresh_config()


@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code

    error_details = {
        "status": "error",
        "error": str(e),
        "error_type": e.__class__.__name__,
        "traceback": traceback.format_exc(),
    }

    # Log level based on error type:
    # - 4xx client errors (404, 400, etc): SEV3 (info) - not our fault
    # - 5xx server errors: SEV0 (emergency) - something broke
    if code >= 500:
        debug_log(0, f"Server error occurred: {error_details}")
    elif code >= 400:
        debug_log(
            3,
            f"Client error: {code} {e.__class__.__name__} - {request.method} {request.path}",
        )

    return error_details, code


# GET/READ Operations


_HINT_ACTIVE_STATES = "('queued','ready','submitted')"

_HINT_QUERY = """SELECT h.id, h.puzzle_id, h.solver, h.queue_position,
                      h.request_text, h.status, h.created_at, h.answered_at,
                      h.submitted_at, p.name AS puzzle_name
               FROM hint h
               LEFT JOIN puzzle p ON h.puzzle_id = p.id
               WHERE h.status IN """ + _HINT_ACTIVE_STATES + """
               ORDER BY h.queue_position ASC"""


def _format_hint_row(row):
    """Format a hint database row into a JSON-safe dict."""
    return {
        "id": row["id"],
        "puzzle_id": row["puzzle_id"],
        "puzzle_name": row["puzzle_name"],
        "solver": row["solver"],
        "queue_position": row["queue_position"],
        "request_text": row["request_text"],
        "status": row["status"],
        "created_at": row["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ") if row["created_at"] else None,
        "answered_at": row["answered_at"].strftime("%Y-%m-%dT%H:%M:%SZ") if row["answered_at"] else None,
        "submitted_at": row["submitted_at"].strftime("%Y-%m-%dT%H:%M:%SZ") if row.get("submitted_at") else None,
    }


def _promote_top_hint(cursor):
    """If the hint at position 1 is 'queued', auto-promote it to 'ready'.
    Does nothing if the top hint is already 'ready' or 'submitted'."""
    cursor.execute(
        "SELECT id, status FROM hint WHERE queue_position = 1 AND status IN ('queued','ready','submitted')"
    )
    top = cursor.fetchone()
    if top and top["status"] == "queued":
        cursor.execute("UPDATE hint SET status = 'ready' WHERE id = %s", (top["id"],))
        debug_log(3, "Auto-promoted hint %d to 'ready'" % top["id"])


def _get_all_from_db():
    """Internal function to fetch all rounds/puzzles from database."""
    debug_log(4, "fetching all from database")
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT * from puzzle_view")
        puzzle_view = cursor.fetchall()
    except Exception:
        raise Exception("Exception in querying puzzle_view")

    all_puzzles = {}
    for puzzle in puzzle_view:
        all_puzzles[puzzle["id"]] = puzzle

    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT * from round_view")
        round_view = cursor.fetchall()
    except Exception:
        raise Exception("Exception in querying round_view")

    def is_int(val):
        try:
            int(val)
            return True
        except Exception:
            return False

    rounds = []
    for round in round_view:
        if "puzzles" in round and round["puzzles"]:
            round["puzzles"] = [
                all_puzzles[int(id)]
                for id in round["puzzles"].split(",")
                if is_int(id) and int(id) in all_puzzles
            ]
        else:
            round["puzzles"] = []
        rounds.append(round)

    try:
        conn, cursor = _read_cursor()
        cursor.execute(_HINT_QUERY)
        hint_rows = cursor.fetchall()
    except Exception:
        raise Exception("Exception in querying hint table")

    hints = [_format_hint_row(row) for row in hint_rows]

    return {"rounds": rounds, "hints": hints}


def _get_all_with_cache():
    """Get all rounds/puzzles, using cache if available."""
    debug_log(4, "start")

    # Ensure memcache is initialized (lazy init on first request)
    ensure_memcache_initialized(mysql.connection)

    # Try cache first if memcache is enabled
    if pbcachelib.mc is not None:
        cached = cache_get(MEMCACHE_CACHE_KEY)
        if cached:
            debug_log(4, "cache hit")
            increment_cache_stat("cache_hits_total", mysql.connection)
            return json.loads(cached)
        debug_log(4, "cache miss")
        increment_cache_stat("cache_misses_total", mysql.connection)

    # Fall back to database
    data = _get_all_from_db()

    # Store in cache for next time (if enabled)
    if pbcachelib.mc is not None:
        try:
            cache_set(MEMCACHE_CACHE_KEY, json.dumps(data), ttl=MEMCACHE_TTL)
        except Exception as e:
            debug_log(3, "failed to cache: %s" % str(e))

    return data


@app.route("/all", endpoint="all", methods=["GET"])
@swag_from("swag/getall.yaml", endpoint="all", methods=["GET"])
def get_all_all():
    """Get all rounds and puzzles (uses cache if available)."""
    return _get_all_with_cache()


@app.route("/allcached", endpoint="allcached", methods=["GET"])
@swag_from("swag/getallcached.yaml", endpoint="allcached", methods=["GET"])
def get_all_cached():
    """Get all rounds and puzzles (uses cache if available). Alias for /all."""
    return _get_all_with_cache()


@app.route("/huntinfo", endpoint="huntinfo", methods=["GET"])
@swag_from("swag/gethuntinfo.yaml", endpoint="huntinfo", methods=["GET"])
def get_hunt_info():
    """Get static hunt info: config, statuses, and tags - for reducing HTTP round-trips"""
    debug_log(5, "start")
    result = {"status": "ok"}

    conn, cursor = _read_cursor()

    # Config
    try:
        cursor.execute("SELECT * FROM config")
        config_rows = cursor.fetchall()
        result["config"] = {row["key"]: row["val"] for row in config_rows}
    except Exception as e:
        debug_log(2, "Could not fetch config: %s" % e)
        result["config"] = {}

    # Statuses - return rich objects with metadata
    try:
        # Get status names from DB ENUM
        status_names = _get_status_names()

        # Parse metadata from config
        status_metadata = {}
        try:
            metadata_json = configstruct.get("STATUS_METADATA", "[]")
            metadata_list = json.loads(metadata_json)
            status_metadata = {item["name"]: item for item in metadata_list}
        except Exception as e:
            debug_log(2, "Could not parse STATUS_METADATA: %s" % e)

        # Build rich status objects
        status_list = []
        for status_name in status_names:
            if status_name in status_metadata:
                meta = status_metadata[status_name]
                status_list.append({
                    "name": status_name,
                    "emoji": meta.get("emoji", "❓"),
                    "text": meta.get("text", status_name[0]),
                    "order": meta.get("order", 50)
                })
            else:
                # Fallback for statuses without metadata
                status_list.append({
                    "name": status_name,
                    "emoji": "❓",
                    "text": status_name[0] if status_name else "?",
                    "order": 50
                })

        # Sort by display order
        status_list.sort(key=lambda x: x["order"])
        result["statuses"] = status_list
    except Exception as e:
        debug_log(2, "Could not fetch statuses: %s" % e)
        result["statuses"] = []

    # Tags
    try:
        cursor.execute("SELECT id, name FROM tag ORDER BY name")
        result["tags"] = cursor.fetchall()
    except Exception as e:
        debug_log(2, "Could not fetch tags: %s" % e)
        result["tags"] = []

    return result


@app.route("/puzzles", endpoint="puzzles", methods=["GET"])
@swag_from("swag/getpuzzles.yaml", endpoint="puzzles", methods=["GET"])
def get_all_puzzles():
    debug_log(4, "start")
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT id, name from puzzle")
        puzzlist = cursor.fetchall()
    except IndexError:
        raise Exception("Exception in fetching all puzzles from database")

    debug_log(4, "listed all puzzles")
    return {
        "status": "ok",
        "puzzles": puzzlist,
    }


def get_puzzles_by_tag_id(tag_id):
    """Get all puzzles with a specific tag ID. Reusable helper function."""
    debug_log(4, "start with tag_id: %s" % tag_id)
    conn, cursor = _read_cursor()

    # Use MEMBER OF() to leverage the multi-valued JSON index
    # Return full puzzle data from puzzle_view to avoid N+1 queries on client
    cursor.execute(
        """SELECT pv.* FROM puzzle_view pv
           JOIN puzzle p ON p.id = pv.id
           WHERE %s MEMBER OF(p.tags)""",
        (tag_id,),
    )
    puzzlist = cursor.fetchall()

    debug_log(4, "found %d puzzles with tag_id %s" % (len(puzzlist), tag_id))
    return puzzlist


def get_tag_id_by_name(tag_name):
    """Get tag ID by name (case-insensitive). Returns None if not found."""
    debug_log(4, "start with tag_name: %s" % tag_name)
    conn, cursor = _read_cursor()
    cursor.execute("SELECT id FROM tag WHERE LOWER(name) = LOWER(%s)", (tag_name,))
    tag_row = cursor.fetchone()
    if not tag_row:
        debug_log(4, "tag '%s' not found" % tag_name)
        return None
    return tag_row["id"]


@app.route("/search", endpoint="search", methods=["GET"])
@swag_from("swag/getsearch.yaml", endpoint="search", methods=["GET"])
def search_puzzles():
    """Search puzzles by tag name or tag ID"""
    debug_log(4, "start")

    tag_name = request.args.get("tag")
    tag_id = request.args.get("tag_id")

    if not tag_name and not tag_id:
        return {
            "status": "error",
            "error": "Must provide 'tag' or 'tag_id' parameter",
        }, 400

    try:
        # If tag name provided, look up the tag_id first
        if tag_name:
            tag_id = get_tag_id_by_name(tag_name)
            if tag_id is None:
                return {"status": "ok", "puzzles": []}
        else:
            # Validate tag_id is an integer
            try:
                tag_id = int(tag_id)
            except (ValueError, TypeError):
                return {"status": "error", "error": "tag_id must be an integer"}, 400

            # Verify the tag exists
            conn, cursor = _read_cursor()
            cursor.execute("SELECT id FROM tag WHERE id = %s", (tag_id,))
            if not cursor.fetchone():
                debug_log(4, "tag_id %s not found" % tag_id)
                return {"status": "ok", "puzzles": []}

        puzzlist = get_puzzles_by_tag_id(tag_id)
        return {
            "status": "ok",
            "puzzles": puzzlist,
        }

    except Exception as e:
        debug_log(1, "Error searching puzzles: %s" % str(e))
        raise Exception(f"Exception searching puzzles: {e}")


@app.route("/rbac/<priv>/<uid>", endpoint="rbac_priv_uid", methods=["GET"])
@swag_from("swag/getrbacprivuid.yaml", endpoint="rbac_priv_uid", methods=["GET"])
def check_priv(priv, uid):
    debug_log(4, "start. priv: %s, uid: %s" % (priv, uid))
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT * FROM privs WHERE uid = %s", (uid,))
        rv = cursor.fetchone()
    except Exception:
        raise Exception("Exception querying database for privs)")

    debug_log(4, "in database user %s ACL is %s" % (uid, rv))

    # Build dict of all privs for this user (the query already fetched them all)
    all_privs = {}
    if rv is not None:
        for key in rv:
            if key != "uid":
                all_privs[key] = rv[key] == "YES"

    try:
        allowed = all_privs.get(priv, False)
    except Exception:
        raise Exception(
            f"Exception in reading priv {priv} from user {uid} ACL. No such priv?"
        )

    return {
        "status": "ok",
        "allowed": allowed,
        "all_privs": all_privs,
    }


@app.route("/puzzles/<id>", endpoint="puzzle_id", methods=["GET"])
@swag_from("swag/getpuzzleid.yaml", endpoint="puzzle_id", methods=["GET"])
def get_one_puzzle(id):
    debug_log(4, "start. id: %s" % id)
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT * from puzzle_view where id = %s", (id,))
        puzzle = cursor.fetchone()
    except IndexError:
        raise Exception(f"Puzzle {id} not found in database")
    except Exception:
        raise Exception(f"Exception in fetching puzzle {id} from database")

    debug_log(5, "fetched puzzle %s: %s" % (id, puzzle))

    # Include lastact to reduce HTTP round-trips for clients
    return {
        "status": "ok",
        "puzzle": puzzle,
        "lastact": get_last_activity_for_puzzle(id),
    }


@app.route("/puzzles/<id>/<part>", endpoint="puzzle_part", methods=["GET"])
@swag_from("swag/getpuzzlepart.yaml", endpoint="puzzle_part", methods=["GET"])
def get_puzzle_part(id, part):
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    if part == "lastact":
        rv = get_last_activity_for_puzzle(id)
    elif part == "lastsheetact":
        rv = get_last_sheet_activity_for_puzzle(id)
    else:
        try:
            conn, cursor = _read_cursor()
            cursor.execute(
                f"SELECT {part} from puzzle_view where id = %s LIMIT 1", (id,)
            )
            rv = cursor.fetchone()[part]
        except TypeError:
            raise Exception(f"Puzzle {id} not found in database")
        except Exception:
            raise Exception(
                f"Exception in fetching {part} part for puzzle {id} from database"
            )

    debug_log(4, "fetched puzzle part %s for %s" % (part, id))
    return {"status": "ok", "puzzle": {"id": id, part: rv}}


@app.route("/puzzles/<id>/activity", endpoint="puzzle_activity", methods=["GET"])
@swag_from("swag/getpuzzleactivity.yaml", endpoint="puzzle_activity", methods=["GET"])
def get_puzzle_activity(id):
    """Get all activity for a specific puzzle."""
    debug_log(4, "start. id: %s" % id)

    # Check if puzzle exists
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT id FROM puzzle WHERE id = %s", (id,))
        if not cursor.fetchone():
            raise Exception(f"Puzzle {id} not found")
    except Exception as e:
        raise Exception(f"Puzzle {id} not found in database")

    # Fetch all activity for this puzzle
    try:
        cursor.execute(
            """
            SELECT id, time, solver_id, puzzle_id, source, type, uri, source_version
            FROM activity
            WHERE puzzle_id = %s
            ORDER BY time DESC
            """,
            (id,),
        )
        activities = cursor.fetchall()
    except Exception as e:
        raise Exception(f"Exception fetching activity for puzzle {id}: {e}")

    debug_log(4, "fetched %d activity entries for puzzle %s" % (len(activities), id))
    return {
        "status": "ok",
        "puzzle_id": int(id),
        "activity": activities,
    }


@app.route("/rounds", endpoint="rounds", methods=["GET"])
@swag_from("swag/getrounds.yaml", endpoint="rounds", methods=["GET"])
def get_all_rounds():
    debug_log(4, "start")
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT id, name from round")
        roundlist = cursor.fetchall()
    except Exception:
        raise Exception("Exception in fetching all rounds from database")

    debug_log(4, "listed all rounds")
    return {
        "status": "ok",
        "rounds": roundlist,
    }


@app.route("/rounds/<id>", endpoint="round_id", methods=["GET"])
@swag_from("swag/getroundid.yaml", endpoint="round_id", methods=["GET"])
def get_one_round(id):
    debug_log(4, "start. id: %s" % id)
    try:
        conn, cursor = _read_cursor()
        cursor.execute(
            """
            SELECT r.id, r.name, r.round_uri, r.drive_uri, r.drive_id, r.status, r.comments,
                   GROUP_CONCAT(p.id) as puzzles
            FROM round r
            LEFT JOIN puzzle p ON p.round_id = r.id
            WHERE r.id = %s
            GROUP BY r.id
        """,
            (id,),
        )
        round = cursor.fetchone()
        if not round:
            raise Exception(f"Round {id} not found in database")

        # Convert puzzles string to list of puzzle objects
        puzzle_ids = round["puzzles"].split(",") if round["puzzles"] else []
        puzzles = []
        for pid in puzzle_ids:
            if pid:  # Skip empty strings
                puzzles.append(get_one_puzzle(pid)["puzzle"])
        round["puzzles"] = puzzles
    except Exception:
        raise Exception(f"Exception in fetching round {id} from database")

    debug_log(4, "fetched round %s" % id)
    return {
        "status": "ok",
        "round": round,
    }


@app.route("/rounds/<id>/<part>", endpoint="round_part", methods=["GET"])
@swag_from("swag/getroundpart.yaml", endpoint="round_part", methods=["GET"])
def get_round_part(id, part):
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    try:
        conn, cursor = _read_cursor()
        # Use round table directly instead of round_view to get status
        cursor.execute(f"SELECT {part} from round where id = %s", (id,))
        answer = cursor.fetchone()
        if not answer:
            raise Exception(f"Round {id} not found in database")
        answer = answer[part]
    except TypeError:
        raise Exception(f"Round {id} not found in database")
    except Exception:
        raise Exception(
            f"Exception in fetching {part} part for round {id} from database"
        )

    if part == "puzzles":
        answer = get_puzzles_from_list(answer)

    debug_log(4, "fetched round part %s for %s" % (part, id))
    return {"status": "ok", "round": {"id": id, part: answer}}


@app.route("/solvers", endpoint="solvers", methods=["GET"])
@swag_from("swag/getsolvers.yaml", endpoint="solvers", methods=["GET"])
def get_all_solvers():
    debug_log(4, "start")
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT id, name, fullname, chat_uid, chat_name from solver")
        solvers = cursor.fetchall()
    except Exception:
        raise Exception("Exception in fetching all solvers from database")

    debug_log(4, "listed all solvers")
    return {"status": "ok", "solvers": solvers}


@app.route("/solvers/<id>", endpoint="solver_id", methods=["GET"])
@swag_from("swag/getsolverid.yaml", endpoint="solver_id", methods=["GET"])
def get_one_solver(id):
    debug_log(4, "start. id: %s" % id)
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT * from solver_view where id = %s", (id,))
        solver = cursor.fetchone()
        if solver is None:
            raise Exception(f"Solver {id} not found in database")
    except IndexError:
        raise Exception(f"Solver {id} not found in database")
    except Exception:
        raise Exception(f"Exception in fetching solver {id} from database")

    solver["lastact"] = get_last_activity_for_solver(id)
    debug_log(4, "fetched solver %s" % id)
    return {
        "status": "ok",
        "solver": solver,
    }


@app.route("/solvers/byname/<name>", endpoint="solver_byname", methods=["GET"])
@swag_from("swag/getsolverbyname.yaml", endpoint="solver_byname", methods=["GET"])
def get_solver_by_name(name):
    """Get solver by username - more efficient than fetching all solvers"""
    debug_log(4, "start. name: %s" % name)
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT * from solver_view where name = %s", (name,))
        solver = cursor.fetchone()
        if solver is None:
            return {"status": "error", "error": f"Solver '{name}' not found"}, 404
    except Exception as e:
        raise Exception(
            f"Exception in fetching solver '{name}' from database: {e}"
        )

    debug_log(4, "fetched solver by name: %s" % name)
    return {
        "status": "ok",
        "solver": solver,
    }


@app.route("/solvers/<id>/activity", endpoint="solver_activity", methods=["GET"])
@swag_from("swag/getsolveractivity.yaml", endpoint="solver_activity", methods=["GET"])
def get_solver_activity(id):
    """Get all activity for a specific solver."""
    debug_log(4, "start. id: %s" % id)

    # Check if solver exists
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT id FROM solver WHERE id = %s", (id,))
        if not cursor.fetchone():
            raise Exception(f"Solver {id} not found")
    except Exception as e:
        raise Exception(f"Solver {id} not found in database")

    # Fetch all activity for this solver
    try:
        cursor.execute(
            """
            SELECT id, time, solver_id, puzzle_id, source, type, uri, source_version
            FROM activity
            WHERE solver_id = %s
            ORDER BY time DESC
            """,
            (id,),
        )
        activities = cursor.fetchall()
    except Exception as e:
        raise Exception(f"Exception fetching activity for solver {id}: {e}")

    debug_log(4, "fetched %d activity entries for solver %s" % (len(activities), id))
    return {
        "status": "ok",
        "solver_id": int(id),
        "activity": activities,
    }


def _solver_exists(identifier):
    """
    Internal check if solver exists. Returns True/False.
    Accepts either an integer id or a string username.
    Does not raise exceptions or log errors for missing solvers.
    """
    try:
        conn, cursor = _read_cursor()

        # Check by id if integer, by name if string
        if isinstance(identifier, int):
            cursor.execute("SELECT id FROM solver WHERE id = %s", (identifier,))
        else:
            cursor.execute("SELECT id FROM solver WHERE name = %s", (identifier,))

        solver = cursor.fetchone()
        return solver is not None
    except Exception as e:
        debug_log(1, "Error checking solver existence for %s: %s" % (identifier, e))
        return False


def _update_single_solver_part(id, part, value, source="puzzleboss"):
    """
    Internal helper to update a single solver part.
    Returns the updated value.
    Raises Exception on error.
    """
    # Special handling for puzzle assignment
    if part == "puzz":
        current_puzzle = None  # Initialize to avoid NameError

        if value:
            # Assigning puzzle, so check if puzzle is real
            debug_log(4, "trying to assign solver %s to puzzle %s" % (id, value))
            mypuzz = get_one_puzzle(value)
            debug_log(5, "return value from get_one_puzzle %s is %s" % (value, mypuzz))
            if mypuzz["status"] != "ok":
                raise Exception(
                    f"Error retrieving info on puzzle {value}, which user {id} is attempting to claim"
                )
            # Reject assignment to solved puzzles
            if mypuzz["puzzle"]["status"] == "Solved":
                raise Exception(
                    f"Cannot assign solver to puzzle {value} - puzzle is already solved"
                )
            # Since we're assigning, the puzzle should automatically transit out of "New" or "Abandoned" state
            if mypuzz["puzzle"]["status"] in ["New", "Abandoned"]:
                debug_log(
                    3,
                    "Automatically marking puzzle id %s, name %s (status: %s) as being worked on."
                    % (mypuzz["puzzle"]["id"], mypuzz["puzzle"]["name"], mypuzz["puzzle"]["status"]),
                )
                update_puzzle_part_in_db(value, "status", "Being worked")

            # Assign the solver to the puzzle using the new JSON-based system
            assign_solver_to_puzzle(value, id, mysql.connection)
        else:
            # Puzz is empty, so this is a de-assignment
            # Find the puzzle the solver is currently assigned to
            conn, cursor = _cursor()
            cursor.execute(
                """
                SELECT id FROM puzzle
                WHERE JSON_CONTAINS(current_solvers,
                    JSON_OBJECT('solver_id', %s),
                    '$.solvers'
                )
            """,
                (id,),
            )
            current_puzzle = cursor.fetchone()
            if current_puzzle:
                # Unassign the solver from their current puzzle
                unassign_solver_from_puzzle(current_puzzle["id"], id, mysql.connection)

        # Now log it in the activity table
        # For de-assignment (empty value), use the actual puzzle_id we found
        # For assignment (non-empty value), use the provided puzzle_id
        puzzle_id_for_log = current_puzzle["id"] if (not value and current_puzzle) else value

        if puzzle_id_for_log:  # Only log if we have a valid puzzle_id
            _log_activity(puzzle_id_for_log, "interact", id, source)

        debug_log(4, "Activity table updated: solver %s taking puzzle %s" % (id, value))
        debug_log(3, "solver %s puzz updated to %s" % (id, value))
        return value

    # For all other parts, just try to update - MySQL will reject invalid columns
    try:
        conn, cursor = _cursor()
        cursor.execute(f"UPDATE solver SET {part} = %s WHERE id = %s", (value, id))
        conn.commit()
    except Exception as e:
        raise Exception(
            f"Exception in modifying {part} of solver {id}: {e}"
        )

    debug_log(3, "solver %s %s updated in database" % (id, part))
    return value


@app.route("/solvers/<id>", endpoint="post_solver_id", methods=["POST"])
@swag_from("swag/postsolver.yaml", endpoint="post_solver_id", methods=["POST"])
def update_solver_multi(id):
    """Update multiple solver parts in a single call."""
    debug_log(4, "start. id: %s" % id)
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")

    if not data or not isinstance(data, dict):
        raise Exception("Expected JSON object with solver parts to update")

    # Check if this is a legit solver
    mysolver = get_one_solver(id)
    debug_log(5, "return value from get_one_solver %s is %s" % (id, mysolver))
    if "status" not in mysolver or mysolver["status"] != "ok":
        raise Exception(f"Error looking up solver {id}")

    # Get source for activity logging if provided
    source = data.pop("source", "puzzleboss") if "source" in data else "puzzleboss"

    updated_parts = {}
    needs_cache_invalidation = False

    for part, value in data.items():
        updated_value = _update_single_solver_part(id, part, value, source)
        updated_parts[part] = updated_value
        if part == "puzz":
            needs_cache_invalidation = True

    # Invalidate cache if puzzle assignment changed
    if needs_cache_invalidation:
        invalidate_cache_with_stats()

    return {"status": "ok", "solver": {"id": id, **updated_parts}}


@app.route("/solvers/<id>/<part>", endpoint="post_solver_part", methods=["POST"])
@swag_from("swag/putsolverpart.yaml", endpoint="post_solver_part", methods=["POST"])
def update_solver_part(id, part):
    """Update a single solver part."""
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
        value = data[part]
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception(f"Expected {part} field missing")

    # Check if this is a legit solver
    mysolver = get_one_solver(id)
    debug_log(5, "return value from get_one_solver %s is %s" % (id, mysolver))
    if "status" not in mysolver or mysolver["status"] != "ok":
        raise Exception(f"Error looking up solver {id}")

    # Get source for activity logging if provided
    source = data.get("source", "puzzleboss")

    updated_value = _update_single_solver_part(id, part, value, source)

    # Invalidate /allcached if solver assignment changed
    if part == "puzz":
        invalidate_cache_with_stats()

    return {"status": "ok", "solver": {"id": id, part: updated_value}}


@app.route("/config", endpoint="getconfig", methods=["GET"])
# @swag_from("swag/getconfig.yaml", endpoint="getconfig", methods=["GET"])
def get_config():
    debug_log(5, "start")
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT * FROM config")
        config = {row["key"]: row["val"] for row in cursor.fetchall()}
    except TypeError:
        raise Exception("Exception fetching config info from database")

    debug_log(5, "fetched all configuration values from database")
    return {"status": "ok", "config": config}


# POST/WRITE Operations


@app.route("/config", endpoint="putconfig", methods=["POST"])
# @swag_from("swag/putconfig.yaml", endpoint="putconfig", methods=["POST"])
def put_config():
    debug_log(4, "start")
    try:
        data = request.get_json()
        mykey = data["cfgkey"]
        myval = data["cfgval"]
        debug_log(
            3,
            "Config change attempt.  struct: %s key %s val %s"
            % (str(data), mykey, myval),
        )
    except Exception as e:
        raise Exception(f"Exception Interpreting input data for config change: {e}")
    conn, cursor = _cursor()
    cursor.execute(
        "INSERT INTO config (`key`, `val`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `key`=%s, `val`=%s",
        (mykey, myval, mykey, myval),
    )
    conn.commit()

    debug_log(2, "Config value %s changed successfully" % mykey)
    return {"status": "ok"}


@app.route("/botstats", endpoint="getbotstats", methods=["GET"])
@swag_from("swag/getbotstats.yaml", endpoint="getbotstats", methods=["GET"])
def get_botstats():
    """Get all bot statistics"""
    debug_log(5, "start")
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT `key`, `val`, `updated` FROM botstats")
        rows = cursor.fetchall()
        botstats = {}
        for row in rows:
            botstats[row["key"]] = {
                "val": row["val"],
                "updated": row["updated"].strftime("%Y-%m-%dT%H:%M:%SZ")
                if row["updated"]
                else None,
            }
    except Exception as e:
        raise Exception(f"Exception fetching botstats from database: {e}")

    debug_log(5, "fetched all botstats from database")
    return {"status": "ok", "botstats": botstats}


@app.route("/botstats", endpoint="putbotstats", methods=["POST"])
@swag_from("swag/putbotstats.yaml", endpoint="putbotstats", methods=["POST"])
def put_botstats():
    """Update multiple bot statistics in a single call"""
    debug_log(4, "start batch botstats update")
    try:
        data = request.get_json()

        # Support both array format and object/dict format
        stats_to_update = []

        if isinstance(data, list):
            # Array format: [{"key": "k1", "val": "v1"}, {"key": "k2", "val": "v2"}]
            for item in data:
                if not isinstance(item, dict) or "key" not in item or "val" not in item:
                    raise Exception("Each item in array must be an object with 'key' and 'val' properties")
                stats_to_update.append((item["key"], item["val"]))
        elif isinstance(data, dict):
            # Object/dict format: {"k1": "v1", "k2": "v2"}
            for key, val in data.items():
                stats_to_update.append((key, val))
        else:
            raise Exception("Input must be either an array of objects or a dictionary")

        if not stats_to_update:
            raise Exception("No statistics provided for update")

        debug_log(4, "Updating %d botstats" % len(stats_to_update))

    except Exception as e:
        raise Exception(f"Exception interpreting input data for batch botstat update: {e}")

    conn, cursor = _cursor()

    # Update all stats in a single transaction
    for key, val in stats_to_update:
        cursor.execute(
            "INSERT INTO botstats (`key`, `val`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `val`=%s",
            (key, val, val),
        )
        debug_log(5, "Updated botstat: key=%s val=%s" % (key, val))

    conn.commit()

    debug_log(4, "Successfully updated %d botstats" % len(stats_to_update))
    return {"status": "ok", "updated": len(stats_to_update)}


@app.route("/botstats/<key>", endpoint="putbotstat", methods=["POST"])
@swag_from("swag/putbotstat.yaml", endpoint="putbotstat", methods=["POST"])
def put_botstat(key):
    """Update a single bot statistic"""
    debug_log(4, "start with key: %s" % key)
    try:
        data = request.get_json()
        myval = data["val"]
        debug_log(4, "Botstat update: key=%s val=%s" % (key, myval))
    except Exception as e:
        raise Exception(f"Exception interpreting input data for botstat update: {e}")

    conn, cursor = _cursor()
    cursor.execute(
        "INSERT INTO botstats (`key`, `val`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `val`=%s",
        (key, myval, myval),
    )
    conn.commit()

    debug_log(4, "Botstat %s updated successfully to %s" % (key, myval))
    return {"status": "ok"}


# Tag endpoints


@app.route("/statuses", endpoint="getstatuses", methods=["GET"])
@swag_from("swag/getstatuses.yaml", endpoint="getstatuses", methods=["GET"])
def get_statuses():
    """Get all available puzzle statuses from database schema"""
    debug_log(5, "start")
    statuses = _get_status_names()
    if not statuses:
        raise Exception("Could not find status column in puzzle table")
    debug_log(5, "fetched %d statuses from database" % len(statuses))
    return {"status": "ok", "statuses": statuses}


@app.route("/tags", endpoint="gettags", methods=["GET"])
@swag_from("swag/gettags.yaml", endpoint="gettags", methods=["GET"])
def get_tags():
    """Get all tags"""
    debug_log(4, "start")
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT id, name, created_at FROM tag ORDER BY name")
        rows = cursor.fetchall()
        tags = []
        for row in rows:
            tags.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "created_at": row["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
                    if row["created_at"]
                    else None,
                }
            )
    except Exception as e:
        raise Exception(f"Exception fetching tags from database: {e}")

    debug_log(4, "fetched %d tags from database" % len(tags))
    return {"status": "ok", "tags": tags}


@app.route("/tags/<tag>", endpoint="gettag", methods=["GET"])
@swag_from("swag/gettag.yaml", endpoint="gettag", methods=["GET"])
def get_tag(tag):
    """Get a single tag by name"""
    debug_log(4, "start with tag: %s" % tag)
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT id, name, created_at FROM tag WHERE name = %s", (tag,))
        row = cursor.fetchone()
        if row is None:
            debug_log(4, "Tag %s not found" % tag)
            return {"status": "error", "error": f"Tag {tag} not found"}, 404
        tag_data = {
            "id": row["id"],
            "name": row["name"],
            "created_at": row["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
            if row["created_at"]
            else None,
        }
    except Exception as e:
        raise Exception(f"Exception fetching tag {tag} from database: {e}")

    debug_log(4, "fetched tag %s from database" % tag)
    return {"status": "ok", "tag": tag_data}


@app.route("/tags", endpoint="posttag", methods=["POST"])
@swag_from("swag/posttag.yaml", endpoint="posttag", methods=["POST"])
def create_tag():
    """Create a new tag"""
    debug_log(4, "start")
    try:
        data = request.get_json()
        tag_name = data["name"].lower()  # Force lowercase
        debug_log(4, "Creating tag: %s" % tag_name)
    except (TypeError, KeyError):
        raise Exception("Missing or invalid 'name' field in request body")

    # Validate tag name (alphanumeric, hyphens, underscores only)
    if not tag_name or not all(c.isalnum() or c in "-_" for c in tag_name):
        return {
            "status": "error",
            "error": "Tag name must be non-empty and contain only alphanumeric characters, hyphens, or underscores",
        }, 400

    try:
        conn, cursor = _cursor()
        cursor.execute("INSERT INTO tag (name) VALUES (%s)", (tag_name,))
        conn.commit()
        new_id = cursor.lastrowid
    except Exception as e:
        if "Duplicate entry" in str(e):
            debug_log(3, "Tag %s already exists" % tag_name)
            return {"status": "error", "error": f"Tag {tag_name} already exists"}, 409
        raise Exception(f"Exception creating tag {tag_name}: {e}")

    debug_log(3, "Created new tag: %s (id: %d)" % (tag_name, new_id))
    return {"status": "ok", "tag": {"id": new_id, "name": tag_name}}


@app.route("/tags/<tag>", endpoint="deletetag", methods=["DELETE"])
@swag_from("swag/deletetag.yaml", endpoint="deletetag", methods=["DELETE"])
def delete_tag(tag):
    """Delete a tag and remove it from all puzzles"""
    debug_log(4, "start with tag: %s" % tag)
    tag_name = tag.lower()  # Normalize to lowercase

    try:
        conn, cursor = _cursor()

        # First, find the tag id
        cursor.execute("SELECT id FROM tag WHERE name = %s", (tag_name,))
        tag_row = cursor.fetchone()
        if not tag_row:
            debug_log(3, "Tag '%s' not found for deletion" % tag_name)
            return {"status": "error", "error": f"Tag '{tag_name}' not found"}, 404

        tag_id = tag_row["id"]

        # Find all puzzles that have this tag and remove it from them
        cursor.execute("SELECT id, tags FROM puzzle WHERE tags IS NOT NULL")
        puzzles = cursor.fetchall()

        puzzles_updated = 0
        for puzzle in puzzles:
            if puzzle["tags"]:
                current_tags = json.loads(puzzle["tags"])
                if tag_id in current_tags:
                    current_tags.remove(tag_id)
                    new_tags = json.dumps(current_tags) if current_tags else None
                    cursor.execute(
                        "UPDATE puzzle SET tags = %s WHERE id = %s",
                        (new_tags, puzzle["id"]),
                    )
                    puzzles_updated += 1

        # Now delete the tag from the tags table
        cursor.execute("DELETE FROM tag WHERE id = %s", (tag_id,))
        conn.commit()

        debug_log(
            3,
            "Deleted tag '%s' (id: %d), removed from %d puzzle(s)"
            % (tag_name, tag_id, puzzles_updated),
        )
        return {
            "status": "ok",
            "message": f"Tag '{tag_name}' deleted",
            "puzzles_updated": puzzles_updated,
        }

    except Exception as e:
        debug_log(1, "Error deleting tag '%s': %s" % (tag_name, str(e)))
        raise Exception(f"Error deleting tag '{tag_name}': {e}")


@app.route("/puzzles", endpoint="post_puzzles", methods=["POST"])
@swag_from("swag/putpuzzle.yaml", endpoint="post_puzzles", methods=["POST"])
def create_puzzle():
    debug_log(4, "start")
    try:
        puzzle_data = request.get_json()
        debug_log(
            5, f"Incoming puzzle creation payload: {json.dumps(puzzle_data, indent=2)}"
        )
        if not puzzle_data or "puzzle" not in puzzle_data:
            return {"status": "error", "error": "Invalid JSON POST structure"}, 400

        puzzle = puzzle_data["puzzle"]
        name = puzzle.get("name").replace(" ", "")  # Strip spaces from name
        round_id = puzzle.get("round_id")
        puzzle_uri = puzzle.get("puzzle_uri")
        ismeta = puzzle.get("ismeta", False)
        debug_log(5, "request data is - %s" % str(puzzle))
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")

    # Check for duplicate
    try:
        conn, cursor = _cursor()
        cursor.execute("SELECT id FROM puzzle WHERE name = %s LIMIT 1", (name,))
        existing_puzzle = cursor.fetchone()
    except Exception:
        raise Exception(
            "Exception checking database for duplicate puzzle before insert"
        )

    if existing_puzzle:
        raise Exception(f"Duplicate puzzle name {name} detected")

    round_drive_uri = get_round_part(round_id, "drive_uri")["round"]["drive_uri"]
    round_name = get_round_part(round_id, "name")["round"]["name"]
    round_drive_id = round_drive_uri.split("/")[-1]

    # Make new channel so we can get channel id and link (use doc redirect hack since no doc yet)
    drive_uri = f"{configstruct['BIN_URI']}/doc.php?pname={name}"
    chat_channel = chat_create_channel_for_puzzle(
        name, round_name, puzzle_uri, drive_uri
    )
    debug_log(4, "return from creating chat channel: %s" % str(chat_channel))

    try:
        chat_id = chat_channel[0]
        chat_link = chat_channel[1]
    except Exception:
        raise Exception("Error in creating chat channel for puzzle")

    debug_log(4, "chat channel for puzzle %s is made" % name)

    # Create google sheet
    drive_id = create_puzzle_sheet(
        round_drive_id,
        {
            "name": name,
            "roundname": round_name,
            "puzzle_uri": puzzle_uri,
            "chat_uri": chat_link,
        },
    )
    drive_uri = f"https://docs.google.com/spreadsheets/d/{drive_id}/edit#gid=1"

    # Actually insert into the database
    try:
        conn, cursor = _cursor()

        # Store the full puzzle name in UTF-8 as the chat channel name
        # The Discord bot will handle creating a proper channel

        cursor.execute(
            """
            INSERT INTO puzzle
            (name, puzzle_uri, round_id, chat_channel_id, chat_channel_link, chat_channel_name, drive_id, drive_uri, ismeta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                name,
                puzzle_uri,
                round_id,
                chat_id,
                chat_link,
                name,  # Store the full name with emojis intact
                drive_id,
                drive_uri,
                ismeta,
            ),
        )
        conn.commit()
    except MySQLdb._exceptions.IntegrityError:
        raise Exception(
            f"MySQL integrity failure. Does another puzzle with the same name {name} exist?"
        )
    except Exception:
        raise Exception(f"Exception in insertion of puzzle {name} into database")

    # We need to figure out what the ID is that the puzzle got assigned
    try:
        conn, cursor = _cursor()
        cursor.execute("SELECT id FROM puzzle WHERE name = %s", (name,))
        puzzle = cursor.fetchone()
        myid = str(puzzle["id"])

        _log_activity(myid, "create")

        # If this is a meta puzzle, check round completion status
        # This handles unmarking rounds that were previously solved when a new unsolved meta is added
        if ismeta:
            from pblib import check_round_completion
            check_round_completion(round_id, conn)
    except Exception:
        raise Exception("Exception checking database for puzzle after insert")

    # Announce new puzzle in chat
    chat_announce_new(name)

    debug_log(
        3,
        "puzzle %s added to system fully (chat room, spreadsheet, database, etc.)!"
        % name,
    )

    # Invalidate /allcached since new puzzle was created
    invalidate_cache_with_stats()

    return {
        "status": "ok",
        "puzzle": {
            "id": myid,
            "name": name,
            "chat_channel_id": chat_id,
            "chat_link": chat_link,
            "drive_uri": drive_uri,
        },
    }


@app.route("/puzzles/stepwise", endpoint="post_puzzles_stepwise", methods=["POST"])
@swag_from("swag/postpuzzlestepwise.yaml", endpoint="post_puzzles_stepwise", methods=["POST"])
def create_puzzle_stepwise():
    """
    Initiates step-by-step puzzle creation process.
    Validates puzzle data and returns a code for use with /createpuzzle/<code>.
    """
    debug_log(4, "start stepwise puzzle creation")
    try:
        puzzle_data = request.get_json()
        debug_log(
            5, f"Incoming stepwise puzzle creation payload: {json.dumps(puzzle_data, indent=2)}"
        )
        if not puzzle_data or "puzzle" not in puzzle_data:
            return {"status": "error", "error": "Invalid JSON POST structure"}, 400

        puzzle = puzzle_data["puzzle"]
        name = puzzle.get("name", "").replace(" ", "")  # Strip spaces from name
        round_id = puzzle.get("round_id")
        puzzle_uri = puzzle.get("puzzle_uri", "")
        ismeta = puzzle.get("ismeta", False)
        is_speculative = puzzle.get("is_speculative", False)
        debug_log(5, "stepwise request data is - %s" % str(puzzle))
    except TypeError:
        return {"status": "error", "error": "Invalid JSON POST structure or empty POST"}, 400

    # Validate required fields
    if not name or not round_id or not puzzle_uri:
        return {"status": "error", "error": "Missing required fields: name, round_id, puzzle_uri"}, 400

    # Check for duplicate
    try:
        conn, cursor = _cursor()
        cursor.execute("SELECT id FROM puzzle WHERE name = %s LIMIT 1", (name,))
        existing_puzzle = cursor.fetchone()
    except Exception as e:
        return {"status": "error", "error": f"Database error checking for duplicate: {e}"}, 500

    if existing_puzzle:
        return {"status": "error", "error": f"Duplicate puzzle name {name} detected"}, 400

    # Validate round exists
    try:
        round_info = get_round_part(round_id, "name")
        if not round_info or "round" not in round_info:
            return {"status": "error", "error": f"Round ID {round_id} not found"}, 404
    except Exception:
        return {"status": "error", "error": f"Round ID {round_id} not found"}, 404

    # Generate unique code and store request (8 bytes = 16 hex chars, fits varchar(16))
    code = token_hex(8)

    try:
        conn, cursor = _cursor()
        cursor.execute(
            """
            INSERT INTO temp_puzzle_creation
            (code, name, round_id, puzzle_uri, ismeta, is_speculative)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (code, name, round_id, puzzle_uri, ismeta, is_speculative),
        )
        conn.commit()
    except Exception as e:
        debug_log(1, f"Failed to store puzzle creation request: {e}")
        return {"status": "error", "error": f"Failed to store puzzle creation request: {e}"}, 500

    debug_log(3, f"Stepwise puzzle creation request stored with code {code}")

    return {
        "status": "ok",
        "code": code,
        "name": name,
        "message": "Puzzle creation request validated. Use /createpuzzle/<code>?step=N to proceed."
    }


@app.route("/createpuzzle/<code>", endpoint="get_createpuzzle", methods=["GET"])
@swag_from("swag/getcreatepuzzle.yaml", endpoint="get_createpuzzle", methods=["GET"])
def finish_puzzle_creation(code):
    """
    Step-by-step puzzle creation endpoint.

    Steps:
    1. Validate puzzle data (retrieve from temp storage)
    2. Create Discord channel (or skip if SKIP_PUZZCORD)
    3. Create Google Sheet (or skip if SKIP_GOOGLE_API)
    4. Insert puzzle into database
    5. Finalize: set metadata, announce, cleanup temp storage
    """
    debug_log(4, f"finish_puzzle_creation called with code {code}")

    step = request.args.get("step")
    if not step:
        return {"status": "error", "error": "Missing step parameter"}, 400

    try:
        step = int(step)
    except ValueError:
        return {"status": "error", "error": "Step parameter must be an integer"}, 400

    # Retrieve puzzle creation request from temp storage
    try:
        conn, cursor = _cursor()
        cursor.execute(
            "SELECT * FROM temp_puzzle_creation WHERE code = %s",
            (code,)
        )
        req = cursor.fetchone()
    except Exception as e:
        debug_log(1, f"Error retrieving puzzle creation request: {e}")
        return {"status": "error", "error": f"Database error: {e}"}, 500

    if not req:
        return {"status": "error", "error": f"Invalid or expired code: {code}"}, 404

    name = req["name"]
    round_id = req["round_id"]
    puzzle_uri = req["puzzle_uri"]
    ismeta = req["ismeta"]
    is_speculative = req["is_speculative"]

    debug_log(4, f"Processing step {step} for puzzle {name}")

    # Step 1: Validate puzzle data and get round info
    if step == 1:
        try:
            round_drive_uri = get_round_part(round_id, "drive_uri")["round"]["drive_uri"]
            round_name = get_round_part(round_id, "name")["round"]["name"]
            round_drive_id = round_drive_uri.split("/")[-1]

            debug_log(3, f"Step 1: Validated puzzle {name} for round {round_name}")

            return {
                "status": "ok",
                "step": 1,
                "message": f"Validated puzzle data for {name}",
                "round_name": round_name
            }
        except Exception as e:
            debug_log(1, f"Step 1 error: {e}")
            return {"status": "error", "error": f"Validation failed: {e}"}, 500

    # Step 2: Create Discord channel
    elif step == 2:
        if configstruct.get("SKIP_PUZZCORD") == "true":
            debug_log(3, f"Step 2: Skipping Discord channel creation (SKIP_PUZZCORD enabled)")
            return {
                "status": "ok",
                "step": 2,
                "skipped": True,
                "message": "Discord integration disabled"
            }

        try:
            round_name = get_round_part(round_id, "name")["round"]["name"]
            # Use doc redirect hack since no doc yet
            drive_uri = f"{configstruct['BIN_URI']}/doc.php?pname={name}"
            chat_channel = chat_create_channel_for_puzzle(
                name, round_name, puzzle_uri, drive_uri
            )
            debug_log(4, f"Step 2: Created chat channel: {chat_channel}")

            chat_id = chat_channel[0]
            chat_link = chat_channel[1]

            # Store channel info in temp table
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE temp_puzzle_creation
                SET chat_channel_id = %s, chat_channel_link = %s
                WHERE code = %s
                """,
                (chat_id, chat_link, code)
            )
            conn.commit()

            debug_log(3, f"Step 2: Created Discord channel for {name}")

            return {
                "status": "ok",
                "step": 2,
                "message": f"Created Discord channel for {name}",
                "chat_channel_id": chat_id,
                "chat_link": chat_link
            }
        except Exception as e:
            debug_log(1, f"Step 2 error: {e}")
            return {"status": "error", "error": f"Failed to create Discord channel: {e}"}, 500

    # Step 3: Create Google Sheet
    elif step == 3:
        if configstruct.get("SKIP_GOOGLE_API") == "true":
            debug_log(3, f"Step 3: Skipping Google Sheet creation (SKIP_GOOGLE_API enabled)")
            return {
                "status": "ok",
                "step": 3,
                "skipped": True,
                "message": "Google API integration disabled"
            }

        try:
            round_drive_uri = get_round_part(round_id, "drive_uri")["round"]["drive_uri"]
            round_name = get_round_part(round_id, "name")["round"]["name"]
            round_drive_id = round_drive_uri.split("/")[-1]

            chat_link = req.get("chat_channel_link", "")

            drive_id = create_puzzle_sheet(
                round_drive_id,
                {
                    "name": name,
                    "roundname": round_name,
                    "puzzle_uri": puzzle_uri,
                    "chat_uri": chat_link,
                },
            )
            drive_uri = f"https://docs.google.com/spreadsheets/d/{drive_id}/edit#gid=1"

            # Store sheet info in temp table
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE temp_puzzle_creation
                SET drive_id = %s, drive_uri = %s
                WHERE code = %s
                """,
                (drive_id, drive_uri, code)
            )
            conn.commit()

            debug_log(3, f"Step 3: Created Google Sheet for {name}")

            return {
                "status": "ok",
                "step": 3,
                "message": f"Created Google Sheet for {name}",
                "drive_id": drive_id,
                "drive_uri": drive_uri
            }
        except Exception as e:
            debug_log(1, f"Step 3 error: {e}")
            return {"status": "error", "error": f"Failed to create Google Sheet: {e}"}, 500

    # Step 4: Insert puzzle into database
    elif step == 4:
        try:
            chat_id = req.get("chat_channel_id", "")
            chat_link = req.get("chat_channel_link", "")
            drive_id = req.get("drive_id", "")
            drive_uri = req.get("drive_uri", "")

            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO puzzle
                (name, puzzle_uri, round_id, chat_channel_id, chat_channel_link, chat_channel_name, drive_id, drive_uri, ismeta)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    name,
                    puzzle_uri,
                    round_id,
                    chat_id,
                    chat_link,
                    name,  # Store the full name with emojis intact
                    drive_id,
                    drive_uri,
                    ismeta,
                ),
            )
            conn.commit()

            # Get the assigned puzzle ID
            cursor.execute("SELECT id FROM puzzle WHERE name = %s", (name,))
            puzzle = cursor.fetchone()
            myid = str(puzzle["id"])

            _log_activity(myid, "create")

            # If this is a meta puzzle, check round completion status
            # This handles unmarking rounds that were previously solved when a new unsolved meta is added
            if ismeta:
                from pblib import check_round_completion
                check_round_completion(round_id, conn)

            debug_log(3, f"Step 4: Inserted puzzle {name} into database with ID {myid}")

            return {
                "status": "ok",
                "step": 4,
                "message": f"Inserted puzzle {name} into database",
                "puzzle_id": myid
            }
        except MySQLdb._exceptions.IntegrityError as e:
            debug_log(1, f"Step 4 integrity error: {e}")
            return {"status": "error", "error": f"Duplicate puzzle name {name} detected"}, 400
        except Exception as e:
            debug_log(1, f"Step 4 error: {e}")
            return {"status": "error", "error": f"Failed to insert puzzle into database: {e}"}, 500

    # Step 5: Finalize - set status, announce, cleanup
    elif step == 5:
        try:
            # Get puzzle ID
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM puzzle WHERE name = %s", (name,))
            puzzle = cursor.fetchone()
            if not puzzle:
                return {"status": "error", "error": f"Puzzle {name} not found in database"}, 404

            myid = str(puzzle["id"])

            # Set speculative status if needed
            if is_speculative:
                cursor.execute(
                    "UPDATE puzzle SET status = 'Speculative' WHERE id = %s",
                    (myid,)
                )
                conn.commit()
                debug_log(3, f"Set puzzle {name} status to Speculative")

            # Announce new puzzle in chat
            chat_announce_new(name)

            # Invalidate /allcached since new puzzle was created
            invalidate_cache_with_stats()

            # Clean up temp storage
            cursor.execute(
                "DELETE FROM temp_puzzle_creation WHERE code = %s",
                (code,)
            )
            conn.commit()

            debug_log(
                3,
                f"Step 5: Finalized puzzle {name} (ID {myid}) - announced and cleaned up"
            )

            return {
                "status": "ok",
                "step": 5,
                "message": f"Puzzle {name} creation complete!",
                "puzzle_id": myid,
                "is_speculative": is_speculative
            }
        except Exception as e:
            debug_log(1, f"Step 5 error: {e}")
            return {"status": "error", "error": f"Failed to finalize puzzle: {e}"}, 500

    else:
        return {"status": "error", "error": f"Invalid step: {step}. Must be 1-5"}, 400


@app.route("/rounds", endpoint="post_rounds", methods=["POST"])
@swag_from("swag/putround.yaml", endpoint="post_rounds", methods=["POST"])
def create_round():
    debug_log(4, "start")
    try:
        data = request.get_json()
        roundname = sanitize_puzzle_name(data["name"])
        debug_log(5, "request data is - %s" % str(data))
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception("Expected field (name) missing.")

    if not roundname or roundname == "":
        raise Exception("Round with empty name disallowed")

    # Check for duplicate
    try:
        conn, cursor = _cursor()
        cursor.execute("SELECT id FROM round WHERE name = %s LIMIT 1", (roundname,))
        existing_round = cursor.fetchone()
    except Exception:
        raise Exception("Exception checking database for duplicate round before insert")

    if existing_round:
        raise Exception(f"Duplicate round name {roundname} detected")

    chat_status = chat_announce_round(roundname)
    debug_log(4, "return from announcing round in chat is - %s" % str(chat_status))

    if chat_status is None:
        raise Exception("Error in announcing new round in chat")

    debug_log(4, "Making call to create google drive folder for round")
    round_drive_id = create_round_folder(roundname)
    round_drive_uri = f"https://drive.google.com/drive/u/1/folders/{round_drive_id}"
    debug_log(5, "Round drive URI created: %s" % round_drive_uri)
    # Actually insert into the database
    conn, cursor = _cursor()
    cursor.execute(
        "INSERT INTO round (name, drive_uri) VALUES (%s, %s)",
        (roundname, round_drive_uri),
    )
    conn.commit()

    debug_log(
        3, "round %s added to database! drive_uri: %s" % (roundname, round_drive_uri)
    )

    # Invalidate /allcached since new round was created
    invalidate_cache_with_stats()

    return {"status": "ok", "round": {"name": roundname}}


@app.route("/rbac/<priv>/<uid>", endpoint="post_rbac_priv_uid", methods=["POST"])
@swag_from("swag/putrbacprivuid.yaml", endpoint="post_rbac_priv_uid", methods=["POST"])
def set_priv(priv, uid):
    debug_log(4, "start. priv: %s, uid %s" % (priv, uid))
    try:
        data = request.get_json()
        debug_log(4, "post data: %s" % (data))
        value = data["allowed"]
        if value != "YES" and value != "NO":
            raise Exception(
                "Improper privset allowed syntax. e.g. {'allowed':'YES'} or {'allowed':'NO'}"
            )
    except Exception as e:
        raise Exception(f"Error interpreting privset JSON allowed field: {e}")
    debug_log(3, "Attempting privset of uid %s:  %s = %s" % (uid, priv, value))

    # Actually insert into the database
    try:
        conn, cursor = _cursor()
        cursor.execute(
            f"INSERT INTO privs (uid, {priv}) VALUES (%s, %s) ON DUPLICATE KEY UPDATE uid=%s, {priv}=%s",
            (uid, value, uid, value),
        )
        conn.commit()
    except Exception:
        raise Exception(
            f"Error modifying priv table for uid {uid} priv {priv} value {value}. Is priv string valid?"
        )

    return {"status": "ok"}


def _update_single_round_part(id, part, value):
    """
    Internal helper to update a single round part.
    Returns the updated value.
    Raises Exception on error.
    """
    if value == "NULL":
        value = None

    # Just try to update - MySQL will reject invalid columns
    try:
        conn, cursor = _cursor()
        cursor.execute(f"UPDATE round SET {part} = %s WHERE id = %s", (value, id))
        conn.commit()
    except Exception as e:
        raise Exception(
            f"Exception in modifying {part} of round {id}: {e}"
        )

    debug_log(3, "round %s %s updated to %s" % (id, part, value))
    return value


@app.route("/rounds/<id>", endpoint="post_round", methods=["POST"])
@swag_from("swag/postround.yaml", endpoint="post_round", methods=["POST"])
def update_round_multi(id):
    """Update multiple round parts in a single call."""
    debug_log(4, "start. id: %s" % id)
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")

    if not data or not isinstance(data, dict):
        raise Exception("Expected JSON object with round parts to update")

    updated_parts = {}

    for part, value in data.items():
        updated_value = _update_single_round_part(id, part, value)
        updated_parts[part] = updated_value

    # Invalidate cache once after all updates
    invalidate_cache_with_stats()

    return {"status": "ok", "round": {"id": id, **updated_parts}}


@app.route("/rounds/<id>/<part>", endpoint="post_round_part", methods=["POST"])
@swag_from("swag/putroundpart.yaml", endpoint="post_round_part", methods=["POST"])
def update_round_part(id, part):
    """Update a single round part."""
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    try:
        data = request.get_json()
        value = data[part]
        debug_log(5, "request data is - %s" % str(data))
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception(f"Expected field ({part}) missing.")

    updated_value = _update_single_round_part(id, part, value)

    # Invalidate /allcached since round data changed
    invalidate_cache_with_stats()

    return {"status": "ok", "round": {"id": id, part: updated_value}}


@app.route("/solvers", endpoint="post_solver", methods=["POST"])
@swag_from("swag/putsolver.yaml", endpoint="post_solver", methods=["POST"])
def create_solver():
    debug_log(4, "start")
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
        name = sanitize_puzzle_name(data["name"])
        fullname = data["fullname"]
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception("One or more expected fields (name, fullname) missing.")

    # Actually insert into the database
    try:
        conn, cursor = _cursor()
        cursor.execute(
            "INSERT INTO solver (name, fullname) VALUES (%s, %s)", (name, fullname)
        )
        conn.commit()
    except MySQLdb._exceptions.IntegrityError:
        raise Exception(
            f"MySQL integrity failure. Does another solver with the same name {name} exist?"
        )
    except Exception:
        raise Exception(f"Exception in insertion of solver {name} into database")

    debug_log(3, "solver %s added to database!" % name)

    return {"status": "ok", "solver": {"name": name, "fullname": fullname}}


def _update_single_puzzle_part(id, part, value, mypuzzle):
    """
    Internal helper to update a single puzzle part.
    Returns the updated value (may be modified, e.g. uppercased answer).
    Raises Exception on error.
    """
    if part == "lastact":
        set_new_activity_for_puzzle(id, value)

    elif part == "status":
        debug_log(4, "part to update is status")
        if value == "Solved":
            if mypuzzle["puzzle"]["status"] == "Solved":
                raise Exception(
                    f"Puzzle {id} is already solved! Refusing to re-solve."
                )
            # Don't mark puzzle as solved if there is no answer filled in
            if not mypuzzle["puzzle"]["answer"]:
                raise Exception(
                    f"Puzzle {id} has no answer! Refusing to mark as solved."
                )
            else:
                debug_log(
                    3,
                    "Puzzle id %s name %s has been Solved!!!"
                    % (id, mypuzzle["puzzle"]["name"]),
                )
                clear_puzzle_solvers(id, mysql.connection)
                update_puzzle_part_in_db(id, "xyzloc", "")  # Clear location on solve
                update_puzzle_part_in_db(id, part, value)
                chat_announce_solved(mypuzzle["puzzle"]["name"])

                # Check if this is a meta puzzle and if all metas in the round are solved
                if mypuzzle["puzzle"]["ismeta"]:
                    check_round_completion(mypuzzle["puzzle"]["round_id"], mysql.connection)
        elif value in ("Needs eyes", "Critical", "WTF"):
            # These statuses trigger an attention announcement
            update_puzzle_part_in_db(id, part, value)
            chat_announce_attention(mypuzzle["puzzle"]["name"])

            _log_activity(id, "interact")
        else:
            # All other valid statuses (Being worked, Unnecessary, Under control, Waiting for HQ, Grind, etc.)
            update_puzzle_part_in_db(id, part, value)
            _log_activity(id, "interact")

    elif part == "ismeta":
        # When setting a puzzle as meta, just update it directly
        update_puzzle_part_in_db(id, part, value)

        # Check round completion whenever metaness changes
        # This handles both marking rounds as solved AND unmarking them if a new unsolved meta is added
        check_round_completion(mypuzzle["puzzle"]["round_id"], mysql.connection)

    elif part == "xyzloc":
        update_puzzle_part_in_db(id, part, value)

        _log_activity(id, "interact")

        if (value is not None) and (value != ""):
            chat_say_something(
                mypuzzle["puzzle"]["chat_channel_id"],
                f"**ATTENTION:** {mypuzzle['puzzle']['name']} is being worked on at {value}",
            )
        else:
            debug_log(3, "puzzle xyzloc removed. skipping discord announcement")

    elif part == "answer":
        if value != "" and value is not None:
            # Mark puzzle as solved automatically when answer is filled in
            update_puzzle_part_in_db(id, "status", "Solved")
            value = value.upper()
            update_puzzle_part_in_db(id, part, value)
            debug_log(
                3,
                "Puzzle id %s name %s has been Solved!!!"
                % (id, mypuzzle["puzzle"]["name"]),
            )
            clear_puzzle_solvers(id, mysql.connection)
            update_puzzle_part_in_db(id, "xyzloc", "")  # Clear location on solve
            chat_announce_solved(mypuzzle["puzzle"]["name"])

            _log_activity(id, "solve")

            # Check if this is a meta puzzle and if all metas in the round are solved
            if mypuzzle["puzzle"]["ismeta"]:
                check_round_completion(mypuzzle["puzzle"]["round_id"], mysql.connection)

    elif part == "comments":
        update_puzzle_part_in_db(id, part, value)
        chat_say_something(
            mypuzzle["puzzle"]["chat_channel_id"],
            f"**ATTENTION** new comment for puzzle {mypuzzle['puzzle']['name']}: {value}",
        )

        _log_activity(id, "comment")

    elif part == "round":
        update_puzzle_part_in_db(id, part, value)
        # This obviously needs some sanity checking

    elif part == "round_id":
        # Validate that the round exists
        conn, cursor = _cursor()
        cursor.execute("SELECT id FROM round WHERE id = %s", (value,))
        if not cursor.fetchone():
            raise Exception(f"Round ID {value} not found")

        # Update the puzzle's round
        update_puzzle_part_in_db(id, part, value)

        # Notify Discord to move the channel to the new round category
        # Re-fetch puzzle to get current name (in case it was updated earlier in this request)
        updated_puzzle = get_one_puzzle(id)
        chat_announce_move(updated_puzzle["puzzle"]["name"])

        _log_activity(id, "interact")

    elif part == "name":
        # Update puzzle name (strip spaces like in create_puzzle)
        sanitized_name = value.replace(" ", "")
        if not sanitized_name:
            raise Exception("Puzzle name cannot be empty")

        # Check for duplicate names
        conn, cursor = _cursor()
        cursor.execute(
            "SELECT id FROM puzzle WHERE name = %s AND id != %s", (sanitized_name, id)
        )
        if cursor.fetchone():
            raise Exception(f"Duplicate puzzle name {sanitized_name} detected")

        update_puzzle_part_in_db(id, part, sanitized_name)

    elif part == "puzzle_uri":
        # Update puzzle URI
        update_puzzle_part_in_db(id, part, value)

    elif part == "sheetcount":
        # Simple integer update for sheet count (set by bigjimmybot)
        update_puzzle_part_in_db(id, part, value)

    elif part == "tags":
        # Tags manipulation: {"tags": {"add": "tagname"}} or {"tags": {"remove": "tagname"}} or {"tags": {"add_id": 123}} or {"tags": {"remove_id": 123}}
        conn, cursor = _cursor()

        # Get current tags
        cursor.execute("SELECT tags FROM puzzle WHERE id = %s", (id,))
        row = cursor.fetchone()
        current_tags = json.loads(row["tags"]) if row["tags"] else []

        tag_changed = False  # Track if we actually made a change

        if "add" in value:
            # Add by tag name (auto-create if doesn't exist)
            tag_name = value["add"].lower()  # Force lowercase

            # Validate tag name
            if not tag_name or not all(c.isalnum() or c in "-_" for c in tag_name):
                raise Exception(
                    "Tag name must be non-empty and contain only alphanumeric characters, hyphens, or underscores"
                )

            cursor.execute("SELECT id FROM tag WHERE name = %s", (tag_name,))
            tag_row = cursor.fetchone()
            if not tag_row:
                # Auto-create the tag
                cursor.execute("INSERT INTO tag (name) VALUES (%s)", (tag_name,))
                conn.commit()
                tag_id = cursor.lastrowid
                debug_log(3, "Auto-created tag %s (id: %d)" % (tag_name, tag_id))
            else:
                tag_id = tag_row["id"]

            if tag_id not in current_tags:
                current_tags.append(tag_id)
                cursor.execute(
                    "UPDATE puzzle SET tags = %s WHERE id = %s",
                    (json.dumps(current_tags), id),
                )
                conn.commit()
                debug_log(3, "Added tag %s to puzzle %s" % (tag_name, id))
                tag_changed = True
                increment_cache_stat("tags_assigned_total", mysql.connection)
            else:
                debug_log(4, "Tag %s already on puzzle %s" % (tag_name, id))

        elif "add_id" in value:
            # Add by tag ID - validate it's an integer first
            try:
                tag_id = int(value["add_id"])
            except (ValueError, TypeError):
                raise Exception("add_id must be an integer")

            cursor.execute("SELECT name FROM tag WHERE id = %s", (tag_id,))
            tag_row = cursor.fetchone()
            if not tag_row:
                raise Exception(f"Tag id {tag_id} not found")
            if tag_id not in current_tags:
                current_tags.append(tag_id)
                cursor.execute(
                    "UPDATE puzzle SET tags = %s WHERE id = %s",
                    (json.dumps(current_tags), id),
                )
                conn.commit()
                debug_log(3, "Added tag id %s to puzzle %s" % (tag_id, id))
                tag_changed = True
                increment_cache_stat("tags_assigned_total", mysql.connection)
            else:
                debug_log(4, "Tag id %s already on puzzle %s" % (tag_id, id))

        elif "remove" in value:
            # Remove by tag name
            tag_name = value["remove"].lower()  # Force lowercase for lookup
            cursor.execute("SELECT id FROM tag WHERE name = %s", (tag_name,))
            tag_row = cursor.fetchone()
            if not tag_row:
                raise Exception(f"Tag '{tag_name}' not found")
            tag_id = tag_row["id"]
            if tag_id in current_tags:
                current_tags.remove(tag_id)
                cursor.execute(
                    "UPDATE puzzle SET tags = %s WHERE id = %s",
                    (json.dumps(current_tags), id),
                )
                conn.commit()
                debug_log(3, "Removed tag %s from puzzle %s" % (tag_name, id))
                tag_changed = True
            else:
                debug_log(4, "Tag %s not on puzzle %s" % (tag_name, id))

        elif "remove_id" in value:
            # Remove by tag ID - validate it's an integer first
            try:
                tag_id = int(value["remove_id"])
            except (ValueError, TypeError):
                raise Exception("remove_id must be an integer")

            cursor.execute("SELECT name FROM tag WHERE id = %s", (tag_id,))
            tag_row = cursor.fetchone()
            if not tag_row:
                raise Exception(f"Tag id {tag_id} not found")
            if tag_id in current_tags:
                current_tags.remove(tag_id)
                cursor.execute(
                    "UPDATE puzzle SET tags = %s WHERE id = %s",
                    (json.dumps(current_tags), id),
                )
                conn.commit()
                debug_log(3, "Removed tag id %s from puzzle %s" % (tag_id, id))
                tag_changed = True
            else:
                debug_log(4, "Tag id %s not on puzzle %s" % (tag_id, id))

        else:
            raise Exception(
                "Invalid tags operation. Use {add: 'name'}, {add_id: id}, {remove: 'name'}, or {remove_id: id}"
            )

        # Log tag change to activity table using system solver_id (100)
        # Use 'comment' type so it doesn't affect lastsheetact (which tracks 'revise' only)
        if tag_changed:
            _log_activity(id, "comment")

    else:
        # For any other part, just try to update it directly
        # MySQL will reject invalid column names
        update_puzzle_part_in_db(id, part, value)

    debug_log(
        3,
        "puzzle name %s, id %s, part %s has been set to %s"
        % (mypuzzle["puzzle"]["name"], id, part, value),
    )

    return value


@app.route("/puzzles/<id>", endpoint="post_puzzle", methods=["POST"])
@swag_from("swag/postpuzzle.yaml", endpoint="post_puzzle", methods=["POST"])
def update_puzzle_multi(id):
    """Update multiple puzzle parts in a single call."""
    debug_log(4, "start. id: %s" % id)
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")

    if not data or not isinstance(data, dict):
        raise Exception("Expected JSON object with puzzle parts to update")

    # Reject sensitive operations that should use single-part endpoint for safety
    if "answer" in data:
        raise Exception(
            "Cannot update 'answer' via multi-part endpoint. Use POST /puzzles/<id>/answer instead."
        )
    if "status" in data and data["status"] == "Solved":
        raise Exception(
            "Cannot set status to 'Solved' via multi-part endpoint. Use POST /puzzles/<id>/status instead."
        )

    # Check if this is a legit puzzle
    mypuzzle = get_one_puzzle(id)
    debug_log(5, "return value from get_one_puzzle %s is %s" % (id, mypuzzle))
    if "status" not in mypuzzle or mypuzzle["status"] != "ok":
        raise Exception(f"Error looking up puzzle {id}")

    updated_parts = {}

    for part, value in data.items():
        # Strip spaces if this is a name update
        if part == "name":
            value = value.replace(" ", "")

        updated_value = _update_single_puzzle_part(id, part, value, mypuzzle)
        updated_parts[part] = updated_value

    # Invalidate cache once after all updates
    invalidate_cache_with_stats()

    return {"status": "ok", "puzzle": {"id": id, **updated_parts}}


@app.route("/puzzles/<id>/<part>", endpoint="post_puzzle_part", methods=["POST"])
@swag_from("swag/putpuzzlepart.yaml", endpoint="post_puzzle_part", methods=["POST"])
def update_puzzle_part(id, part):
    """Update a single puzzle part."""
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
        value = data[part]
        # Strip spaces if this is a name update
        if part == "name":
            value = value.replace(" ", "")
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception(f"Expected {part} field missing")

    # Check if this is a legit puzzle
    mypuzzle = get_one_puzzle(id)
    debug_log(5, "return value from get_one_puzzle %s is %s" % (id, mypuzzle))
    if "status" not in mypuzzle or mypuzzle["status"] != "ok":
        raise Exception(f"Error looking up puzzle {id}")

    updated_value = _update_single_puzzle_part(id, part, value, mypuzzle)

    # Invalidate cache
    invalidate_cache_with_stats()

    return {"status": "ok", "puzzle": {"id": id, part: updated_value}}


@app.route("/account", endpoint="post_new_account", methods=["POST"])
@swag_from("swag/putnewaccount.yaml", endpoint="post_new_account", methods=["POST"])
def new_account():
    debug_log(4, "start.")
    try:
        data = request.get_json()
        username = data["username"]
        fullname = data["fullname"]
        email = data["email"]
        password = data["password"]
        debug_log(5, "request data: username=%s fullname=%s email=%s password=REDACTED" % (username, fullname, email))
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception(
            "Expected field missing (username, fullname, email, or password)"
        )

    if _solver_exists(username):
        debug_log(
            2,
            "Account creation rejected: username %s already exists" % username,
        )
        return {
            "status": "error",
            "error": f"Username {username} already exists. Use Google's password recovery to reset your password.",
        }, 400

    # Generate the code
    code = token_hex(4)
    debug_log(4, "code picked: %s" % code)

    # Actually insert into the database
    try:
        conn, cursor = _cursor()
        cursor.execute(
            """
            INSERT INTO newuser
            (username, fullname, email, password, code)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (username, fullname, email, password, code),
        )
        conn.commit()
    except TypeError:
        raise Exception(
            f"Exception in insertion of unverified user request {username} into database"
        )

    email_result = email_user_verification(email, code, fullname, username)
    if email_result == "OK":
        debug_log(
            3,
            "unverified new user %s added to database with verification code %s. email sent."
            % (username, code),
        )
        return {"status": "ok", "code": code}

    debug_log(
        2,
        "unverified new user %s added but email failed: %s"
        % (username, email_result),
    )
    return {"status": "ok", "code": code, "email_error": email_result}


@app.route("/finishaccount/<code>", endpoint="get_finish_account", methods=["GET"])
@swag_from("swag/getfinishaccount.yaml", endpoint="get_finish_account", methods=["GET"])
def finish_account(code):
    """
    Account creation endpoint with optional step parameter for progress tracking.

    Steps:
      1 - Validate verification code
      2 - Create Google Workspace account
      3 - Add to solver database (skipped if solver already exists)
      4 - Cleanup (delete temporary newuser entry)

    If no step parameter, runs all steps at once (backward compatible).
    """
    step = request.args.get("step", None)
    debug_log(4, "start. code %s, step %s" % (code, step))

    # Always validate code and get user info first
    try:
        conn, cursor = _cursor()
        cursor.execute(
            """
            SELECT username, fullname, email, password, created_at
            FROM newuser
            WHERE code = %s
            """,
            (code,),
        )
        newuser = cursor.fetchone()

        username = newuser["username"]
        fullname = newuser["fullname"]
        email = newuser["email"]
        password = newuser["password"]
        debug_log(5, "newuser lookup: username=%s fullname=%s email=%s password=REDACTED" % (username, fullname, email))

        # Check code expiration (48 hours)
        import datetime
        created_at = newuser["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)
        age = datetime.datetime.now() - created_at
        if age.total_seconds() > 48 * 3600:
            # Clean up the expired entry
            cursor.execute("DELETE FROM newuser WHERE code = %s", (code,))
            conn.commit()
            raise Exception("Verification code has expired. Please register again.")

    except TypeError:
        raise Exception(f"Code {code} is not valid.")

    debug_log(
        4,
        "valid code. username: %s fullname: %s email: %s password: REDACTED"
        % (username, fullname, email),
    )

    firstname, lastname = fullname.split(maxsplit=1)

    # If no step specified, run all steps (backward compatible)
    if step is None:
        debug_log(
            4, "User %s: Running all steps at once (no step parameter)" % username
        )
        result = add_user_to_google(username, firstname, lastname, password, email)
        if result != "OK":
            raise Exception(f"Failed to create Google account: {result}")
        if not _solver_exists(username):
            conn, cursor = _cursor()
            cursor.execute(
                "INSERT INTO solver (name, fullname) VALUES (%s, %s)",
                (username, f"{firstname} {lastname}"),
            )
            conn.commit()
        conn, cursor = _cursor()
        cursor.execute("""DELETE FROM newuser WHERE code = %s""", (code,))
        conn.commit()
        debug_log(
            4,
            "User %s: All steps complete, temporary newuser entry deleted"
            % username,
        )
        return {"status": "ok"}

    # Step 1: Validate code
    if step == "1":
        debug_log(
            4,
            "User %s: Step 1 - Validation complete"
            % username,
        )
        return {"status": "ok", "step": 1, "operation": "new", "username": username}

    # Step 2: Create Google Workspace account
    if step == "2":
        if configstruct.get("SKIP_GOOGLE_API") == "true":
            debug_log(3, "User %s: Step 2 - Skipping Google account (SKIP_GOOGLE_API enabled)" % username)
            return {"status": "ok", "step": 2, "message": "Google account creation skipped", "skipped": True}
        debug_log(
            4, "User %s: Step 2 - Creating new Google Workspace account" % username
        )
        result = add_user_to_google(username, firstname, lastname, password, email)
        if result != "OK":
            raise Exception(f"Failed to create Google account: {result}")
        debug_log(
            4,
            "User %s: Step 2 - Google Workspace account created successfully"
            % username,
        )
        return {"status": "ok", "step": 2, "message": "Google account created"}

    # Step 3: Add to solver database
    if step == "3":
        debug_log(
            4,
            "User %s: Step 3 - Checking if solver already exists in Puzzleboss database"
            % username,
        )
        if _solver_exists(username):
            debug_log(
                4,
                "User %s: Step 3 - Solver already exists in database, skipping"
                % username,
            )
            return {
                "status": "ok",
                "step": 3,
                "message": "Skipped (solver already exists)",
                "skipped": True,
            }
        debug_log(
            4,
            "User %s: Step 3 - Adding to Puzzleboss solver database"
            % username,
        )
        conn, cursor = _cursor()
        cursor.execute(
            "INSERT INTO solver (name, fullname) VALUES (%s, %s)",
            (username, f"{firstname} {lastname}"),
        )
        conn.commit()
        debug_log(
            4, "User %s: Step 3 - Added to solver database successfully" % username
        )
        return {"status": "ok", "step": 3, "message": "Added to solver database"}

    # Step 4: Cleanup
    # Delete the temporary newuser entry (contains verification code and password)
    if step == "4":
        debug_log(
            4,
            "User %s: Step 4 - Deleting temporary newuser entry from database"
            % username,
        )
        conn, cursor = _cursor()
        cursor.execute("""DELETE FROM newuser WHERE code = %s""", (code,))
        conn.commit()
        debug_log(
            4,
            "User %s: Step 4 - Cleanup complete, account registration finished"
            % username,
        )
        return {"status": "ok", "step": 4, "message": "Cleanup complete"}

    raise Exception(f"Invalid step: {step}")


@app.route("/deleteuser/<username>", endpoint="get_delete_account", methods=["GET"])
@swag_from("swag/getdeleteaccount.yaml", endpoint="get_delete_account", methods=["GET"])
def delete_account(username):
    debug_log(4, "start. username %s" % username)

    delete_pb_solver(username)
    debug_log(3, "user %s deleted from solver db" % username)

    errmsg = delete_google_user(username)

    if errmsg != "OK":
        raise Exception(errmsg)

    debug_log(3, "user %s deleted from Google Workspace" % username)
    return {"status": "ok"}


@app.route("/newusers", endpoint="get_new_users", methods=["GET"])
@swag_from("swag/getnewusers.yaml", endpoint="get_new_users", methods=["GET"])
def get_new_users():
    """Return all pending account registrations from the newuser table."""
    debug_log(4, "start")
    conn, cursor = _read_cursor()
    cursor.execute("SELECT username, fullname, email, code, created_at FROM newuser ORDER BY created_at DESC")
    rows = cursor.fetchall()
    return {"status": "ok", "newusers": rows}


@app.route("/newusers/<code>", endpoint="delete_new_user", methods=["DELETE"])
@swag_from("swag/deletenewuser.yaml", endpoint="delete_new_user", methods=["DELETE"])
def delete_new_user(code):
    """Delete a pending account registration by verification code."""
    debug_log(4, "start. code %s" % code)
    conn, cursor = _cursor()
    cursor.execute("DELETE FROM newuser WHERE code = %s", (code,))
    conn.commit()
    deleted = cursor.rowcount
    if deleted == 0:
        raise Exception(f"No pending account found with code {code}")
    debug_log(3, "pending account with code %s deleted" % code)
    return {"status": "ok"}


@app.route("/privs", endpoint="get_all_privs", methods=["GET"])
@swag_from("swag/getprivs.yaml", endpoint="get_all_privs", methods=["GET"])
def get_all_privs():
    """Return all privilege records from the privs table."""
    debug_log(4, "start")
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT uid, puzztech, puzzleboss FROM privs")
        rows = cursor.fetchall()
    except Exception:
        raise Exception("Exception fetching all privs from database")

    debug_log(4, "listed all privs (%d rows)" % len(rows))
    return {"status": "ok", "privs": rows}


@app.route("/google/users", endpoint="get_google_users", methods=["GET"])
@swag_from("swag/getgoogleusers.yaml", endpoint="get_google_users", methods=["GET"])
def get_google_users():
    """Return all Google Workspace user information. Gracefully empty if Google API is disabled."""
    debug_log(4, "start")

    if configstruct.get("SKIP_GOOGLE_API", "false") == "true":
        debug_log(3, "Google API disabled, returning empty user list")
        return {"status": "ok", "users": [], "google_disabled": True}

    try:
        from googleapiclient.discovery import build
        pbgooglelib.initadmin()
        userservice = build("admin", "directory_v1", credentials=pbgooglelib.admincreds)
        domain = configstruct["DOMAINNAME"]

        users = []
        page_token = None
        while True:
            results = userservice.users().list(
                domain=domain,
                maxResults=500,
                pageToken=page_token,
                projection="full",
            ).execute()

            for user in results.get("users", []):
                primary = user.get("primaryEmail", "")
                username = primary.split("@")[0].lower() if "@" in primary else primary.lower()
                name = user.get("name", {})
                users.append({
                    "username": username,
                    "primaryEmail": primary,
                    "givenName": name.get("givenName", ""),
                    "familyName": name.get("familyName", ""),
                    "fullName": name.get("fullName", ""),
                    "recoveryEmail": user.get("recoveryEmail", ""),
                    "suspended": user.get("suspended", False),
                    "creationTime": user.get("creationTime", ""),
                    "lastLoginTime": user.get("lastLoginTime", ""),
                    "isAdmin": user.get("isAdmin", False),
                    "orgUnitPath": user.get("orgUnitPath", ""),
                })

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        debug_log(4, "fetched %d Google Workspace users" % len(users))
        return {"status": "ok", "users": users}
    except Exception as e:
        debug_log(1, "Failed to fetch Google users: %s" % e)
        return {"status": "ok", "users": [], "error": str(e)}


@app.route("/deletepuzzle/<puzzlename>", endpoint="delete_puzzle", methods=["DELETE"])
@swag_from("swag/deletepuzzle.yaml", endpoint="delete_puzzle", methods=["DELETE"])
def delete_puzzle(puzzlename):
    debug_log(4, "start. delete puzzle named %s" % puzzlename)
    puzzid = get_puzzle_id_by_name(puzzlename)
    if puzzid == 0:
        debug_log(2, "puzzle named %s not found in system!" % puzzlename)
        raise Exception("puzzle not found in system.")
    sheetid = get_puzzle_part(puzzid, "drive_id")["puzzle"]["drive_id"]

    if delete_puzzle_sheet(sheetid) != 0:
        debug_log(
            2,
            "Puzzle id %s deletion request but sheet deletion failed! continuing. this may cause a mess!"
            % puzzid,
        )

    clear_puzzle_solvers(puzzid, mysql.connection)

    try:
        conn, cursor = _cursor()
        cursor.execute("DELETE from puzzle where id = %s", (puzzid,))
        conn.commit()
    except Exception:
        raise Exception(
            f"Puzzle deletion attempt for id {puzzid} name {puzzlename} failed in database operation."
        )

    debug_log(2, "puzzle id %s named %s deleted from system!" % (puzzid, puzzlename))

    # Invalidate /allcached since puzzle was deleted
    invalidate_cache_with_stats()

    return {"status": "ok"}


############### END REST calls section



def get_puzzle_id_by_name(name):
    debug_log(4, "start, called with (name): %s" % name)

    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT id FROM puzzle WHERE name = %s LIMIT 1", (name,))
        rv = cursor.fetchone()["id"]
        debug_log(4, "rv = %s" % rv)
    except Exception:
        debug_log(2, "Puzzle name %s not found in database." % name)
        return 0
    return rv


def update_puzzle_part_in_db(id, part, value):
    conn, cursor = _cursor()

    if part == "solvers":
        # Handle solver assignments
        if value:  # Assign solver
            assign_solver_to_puzzle(id, value, mysql.connection)
        else:  # Clear all solvers
            clear_puzzle_solvers(id, mysql.connection)
    else:
        # Handle other puzzle updates
        cursor.execute(f"UPDATE puzzle SET {part} = %s WHERE id = %s", (value, id))
        conn.commit()

    debug_log(4, "puzzle %s %s updated in database" % (id, part))

    return 0


def get_puzzles_from_list(puzzle_ids):
    debug_log(4, "start, called with: %s" % puzzle_ids)
    if not puzzle_ids:
        return []

    puzlist = puzzle_ids.split(",")
    puzarray = []
    for mypuz in puzlist:
        debug_log(4, "fetching puzzle info for pid: %s" % mypuz)
        puzarray.append(get_one_puzzle(mypuz)["puzzle"])

    debug_log(4, "puzzle list assembled is: %s" % puzarray)
    return puzarray


def get_last_activity_for_puzzle(id):
    debug_log(4, "start, called with: %s" % id)
    try:
        conn, cursor = _read_cursor()
        cursor.execute(
            """SELECT * from activity where puzzle_id = %s ORDER BY time DESC LIMIT 1""",
            (id,),
        )
        return cursor.fetchone()
    except IndexError:
        debug_log(4, "No Activity for Puzzle %s found in database yet" % id)
        return None


def get_last_sheet_activity_for_puzzle(id):
    """Get the last 'revise' type activity for a puzzle (sheet edits only)."""
    debug_log(4, "start, called with: %s" % id)
    try:
        conn, cursor = _read_cursor()
        cursor.execute(
            """SELECT * from activity where puzzle_id = %s AND type = 'revise' ORDER BY time DESC LIMIT 1""",
            (id,),
        )
        return cursor.fetchone()
    except IndexError:
        debug_log(4, "No Sheet Activity for Puzzle %s found in database yet" % id)
        return None


def get_last_activity_for_solver(id):
    debug_log(4, "start, called with: %s" % id)
    try:
        conn, cursor = _read_cursor()
        cursor.execute(
            "SELECT * from activity where solver_id = %s ORDER BY time DESC LIMIT 1",
            (id,),
        )
        return cursor.fetchone()
    except IndexError:
        debug_log(4, "No Activity for solver %s found in database yet" % id)
        return None


def set_new_activity_for_puzzle(id, actstruct):
    debug_log(4, "start, called for puzzle id %s with: %s" % (id, actstruct))

    try:
        solver_id = actstruct["solver_id"]
        source = actstruct["source"]
        activity_type = actstruct["type"]
    except Exception:
        debug_log(
            0,
            "Failure parsing activity dict. Needs solver_id, source, type. dict passed in is: %s"
            % actstruct,
        )
        return 255

    _log_activity(id, activity_type, solver_id, source)
    debug_log(3, "Updated activity for puzzle id %s" % id)
    return 0


def delete_pb_solver(username):
    debug_log(4, "start, called with username %s" % username)

    conn, cursor = _cursor()
    cursor.execute("DELETE from solver where name = %s", (username,))
    conn.commit()
    return 0


def _get_validated_history(puzzle_id):
    """Parse request, validate puzzle+solver, return (solver_id, history, conn, cursor)."""
    data = request.get_json()
    solver_id = data["solver_id"]

    mypuzzle = get_one_puzzle(puzzle_id)
    if "status" not in mypuzzle or mypuzzle["status"] != "ok":
        raise Exception(f"Error looking up puzzle {puzzle_id}")
    mysolver = get_one_solver(solver_id)
    if "status" not in mysolver or mysolver["status"] != "ok":
        raise Exception(f"Error looking up solver {solver_id}")

    conn, cursor = _cursor()
    cursor.execute("SELECT solver_history FROM puzzle WHERE id = %s", (puzzle_id,))
    history_str = cursor.fetchone()["solver_history"] or json.dumps({"solvers": []})
    return solver_id, json.loads(history_str), conn, cursor


@app.route(
    "/puzzles/<id>/history/add", endpoint="add_solver_to_history", methods=["POST"]
)
@swag_from(
    "swag/addsolvertohistory.yaml", endpoint="add_solver_to_history", methods=["POST"]
)
def add_solver_to_history(id):
    debug_log(4, "start. id: %s" % id)
    solver_id, history, conn, cursor = _get_validated_history(id)

    existing_ids = [s["solver_id"] for s in history["solvers"]]
    if solver_id not in existing_ids:
        history["solvers"].append({"solver_id": solver_id})
        cursor.execute(
            "UPDATE puzzle SET solver_history = %s WHERE id = %s",
            (json.dumps(history), id),
        )
        conn.commit()
        debug_log(3, "Added solver %s to history for puzzle %s" % (solver_id, id))
    else:
        debug_log(3, "Solver %s already in history for puzzle %s" % (solver_id, id))

    return {"status": "ok"}


@app.route(
    "/puzzles/<id>/history/remove",
    endpoint="remove_solver_from_history",
    methods=["POST"],
)
@swag_from(
    "swag/removesolverfromhistory.yaml",
    endpoint="remove_solver_from_history",
    methods=["POST"],
)
def remove_solver_from_history(id):
    debug_log(4, "start. id: %s" % id)
    solver_id, history, conn, cursor = _get_validated_history(id)

    history["solvers"] = [s for s in history["solvers"] if s["solver_id"] != solver_id]
    cursor.execute(
        "UPDATE puzzle SET solver_history = %s WHERE id = %s",
        (json.dumps(history), id),
    )
    conn.commit()
    debug_log(3, "Removed solver %s from history for puzzle %s" % (solver_id, id))

    return {"status": "ok"}


@app.route("/cache/invalidate", endpoint="cache_invalidate", methods=["POST"])
@swag_from(
    "swag/postcacheinvalidate.yaml", endpoint="cache_invalidate", methods=["POST"]
)
def force_cache_invalidate():
    """Force invalidation of all caches"""
    debug_log(3, "Cache invalidation requested")
    try:
        invalidate_cache_with_stats()
        return {"status": "ok", "message": "Cache invalidated successfully"}
    except Exception as e:
        debug_log(1, f"Error invalidating cache: {str(e)}")
        return {"status": "error", "error": str(e)}, 500


@app.route("/activity", endpoint="activity", methods=["GET"])
@swag_from("swag/getactivity.yaml", endpoint="activity", methods=["GET"])
def get_all_activities():
    """Get activity counts by type and puzzle timing information."""
    try:
        conn, cursor = _read_cursor()

        # Get activity counts
        cursor.execute(
            """
            SELECT type, COUNT(*) as count 
            FROM activity 
            GROUP BY type
            """
        )
        activities = cursor.fetchall()

        # Get puzzle solve timing information
        cursor.execute(
            """
            SELECT 
                COUNT(DISTINCT a1.puzzle_id) as total_solves,
                SUM(TIMESTAMPDIFF(SECOND, a2.time, a1.time)) as total_solve_time
            FROM activity a1
            JOIN activity a2 ON a1.puzzle_id = a2.puzzle_id AND a2.type = 'create'
            WHERE a1.type = 'solve'
            """
        )
        solve_timing = cursor.fetchone()

        # Get open puzzles timing information
        cursor.execute(
            """
            SELECT 
                COUNT(DISTINCT p.id) as total_open,
                SUM(TIMESTAMPDIFF(SECOND, a.time, NOW())) as total_open_time
            FROM puzzle p
            JOIN activity a ON p.id = a.puzzle_id AND a.type = 'create'
            WHERE p.status != 'Solved' AND p.status != '[hidden]'
            """
        )
        open_timing = cursor.fetchone()

        # Get time since last solve
        cursor.execute(
            """
            SELECT TIMESTAMPDIFF(SECOND, time, NOW()) as seconds_since_last_solve
            FROM activity
            WHERE type = 'solve'
            ORDER BY time DESC
            LIMIT 1
            """
        )
        last_solve = cursor.fetchone()

        cursor.close()

        # Convert to dictionary format for easier access
        activity_counts = {row["type"]: row["count"] for row in activities}

        return {
                "status": "ok",
                "activity": activity_counts,
                "puzzle_solves_timer": {
                    "total_solves": solve_timing["total_solves"] or 0,
                    "total_solve_time_seconds": solve_timing["total_solve_time"] or 0,
                },
                "open_puzzles_timer": {
                    "total_open": open_timing["total_open"] or 0,
                    "total_open_time_seconds": open_timing["total_open_time"] or 0,
                },
                "seconds_since_last_solve": last_solve["seconds_since_last_solve"]
                if last_solve
                else None,
            }
    except Exception as e:
        debug_log(1, "Exception in getting activity counts: %s" % e)
        return {"status": "error", "error": str(e)}, 500


# ============================================================================
# LLM Query Endpoint - Natural language queries about hunt status
# ============================================================================


@app.route("/v1/query", endpoint="llm_query", methods=["POST"])
@swag_from("swag/postquery.yaml", endpoint="llm_query", methods=["POST"])
def llm_query():
    """
    Natural language query endpoint powered by Google Gemini.
    Accepts a text query and returns a natural language response about hunt status.
    Intended for localhost use only (e.g., Discord bot on same server).
    """
    if not GEMINI_AVAILABLE:
        return {"status": "error", "error": "Google Generative AI SDK not installed"}, 503

    # Check for API key in database config
    api_key = configstruct.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"status": "error", "error": "GEMINI_API_KEY not configured in database"}, 503

    # Parse request
    data = request.get_json()
    if not data or "text" not in data:
        return {"status": "error", "error": "Missing 'text' field in request"}, 400

    user_id = data.get("user_id", "unknown")
    query_text = data.get("text", "")

    # Get system instruction from config (required for LLM to be enabled)
    system_instruction = configstruct.get("GEMINI_SYSTEM_INSTRUCTION", "")
    if not system_instruction:
        return {"status": "error", "error": "GEMINI_SYSTEM_INSTRUCTION not configured in database"}, 503

    # Get model from config (required for LLM to be enabled)
    model = configstruct.get("GEMINI_MODEL", "")
    if not model:
        return {"status": "error", "error": "GEMINI_MODEL not configured in database"}, 503

    # Get database cursor for the library
    conn, cursor = _cursor()

    # Process the query using the LLM library
    # Uses cached data when available, falls back to DB
    result = llm_process_query(
        query_text=query_text,
        api_key=api_key,
        system_instruction=system_instruction,
        model=model,
        get_all_data_fn=_get_all_with_cache,
        cursor=cursor,
        user_id=user_id,
        get_last_sheet_activity_fn=get_last_sheet_activity_for_puzzle,
        get_puzzle_id_by_name_fn=get_puzzle_id_by_name,
        get_one_puzzle_fn=get_one_puzzle,
        get_one_solver_fn=get_one_solver,
        get_tag_id_by_name_fn=get_tag_id_by_name,
        get_puzzles_by_tag_id_fn=get_puzzles_by_tag_id,
        wiki_chromadb_path=configstruct.get("WIKI_CHROMADB_PATH", ""),
    )

    if result.get("status") == "error":
        return result, 500

    return result


# ==========================================
# HINT QUEUE ENDPOINTS
# ==========================================


@app.route("/hints", endpoint="gethints", methods=["GET"])
@swag_from("swag/gethints.yaml", endpoint="gethints", methods=["GET"])
def get_hints():
    """Get all active (queued) hint requests, ordered by queue position"""
    debug_log(4, "start")
    try:
        conn, cursor = _read_cursor()
        cursor.execute(_HINT_QUERY)
        rows = cursor.fetchall()
        hints = [_format_hint_row(row) for row in rows]
    except Exception as e:
        raise Exception(f"Exception fetching hints from database: {e}")

    debug_log(4, "fetched %d active hints" % len(hints))
    return {"status": "ok", "hints": hints}


@app.route("/hints", endpoint="posthint", methods=["POST"])
@swag_from("swag/posthint.yaml", endpoint="posthint", methods=["POST"])
def create_hint():
    """Submit a new hint request, adds to end of queue"""
    debug_log(4, "start")
    try:
        data = request.get_json()
        puzzle_id = data["puzzle_id"]
        solver = data["solver"]
        request_text = data["request_text"]
    except (TypeError, KeyError):
        return {"status": "error", "error": "Missing required fields: puzzle_id, solver, request_text"}, 400

    if not request_text or not request_text.strip():
        return {"status": "error", "error": "request_text must be non-empty"}, 400

    try:
        conn, cursor = _cursor()
        cursor.execute("SELECT id FROM puzzle WHERE id = %s", (puzzle_id,))
        if not cursor.fetchone():
            debug_log(3, "Puzzle %s not found for hint creation" % puzzle_id)
            return {"status": "error", "error": f"Puzzle {puzzle_id} not found"}, 404

        cursor.execute(
            "SELECT COALESCE(MAX(queue_position), 0) + 1 AS next_pos FROM hint WHERE status IN " + _HINT_ACTIVE_STATES
        )
        next_pos = cursor.fetchone()["next_pos"]

        initial_status = 'ready' if next_pos == 1 else 'queued'
        cursor.execute(
            """INSERT INTO hint (puzzle_id, solver, queue_position, request_text, status)
               VALUES (%s, %s, %s, %s, %s)""",
            (puzzle_id, solver, next_pos, request_text.strip(), initial_status),
        )
        conn.commit()
        new_id = cursor.lastrowid
    except Exception as e:
        debug_log(1, "Error creating hint: %s" % e)
        raise Exception(f"Exception creating hint: {e}")

    invalidate_cache_with_stats()
    debug_log(3, "Created hint %d for puzzle %s at position %d" % (new_id, puzzle_id, next_pos))
    return {"status": "ok", "hint": {"id": new_id, "queue_position": next_pos}}


@app.route("/hints/count", endpoint="gethintcount", methods=["GET"])
@swag_from("swag/gethintcount.yaml", endpoint="gethintcount", methods=["GET"])
def get_hint_count():
    """Return the count of active (queued) hints"""
    debug_log(4, "start")
    try:
        conn, cursor = _read_cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM hint WHERE status IN " + _HINT_ACTIVE_STATES)
        row = cursor.fetchone()
    except Exception as e:
        raise Exception(f"Exception counting hints: {e}")

    return {"status": "ok", "count": row["count"]}


@app.route("/hints/<int:id>/answer", endpoint="answerhint", methods=["POST"])
@swag_from("swag/answerhint.yaml", endpoint="answerhint", methods=["POST"])
def answer_hint(id):
    """Mark a hint as answered and promote remaining active hints"""
    debug_log(4, "start with hint id: %d" % id)
    try:
        conn, cursor = _cursor()
        cursor.execute(
            "SELECT id, queue_position FROM hint WHERE id = %s AND status IN " + _HINT_ACTIVE_STATES,
            (id,),
        )
        hint = cursor.fetchone()
        if not hint:
            debug_log(3, "Hint %d not found or already answered" % id)
            return {"status": "error", "error": f"Hint {id} not found or already answered"}, 404

        answered_pos = hint["queue_position"]

        cursor.execute(
            "UPDATE hint SET status = 'answered', answered_at = NOW(), queue_position = 0 WHERE id = %s",
            (id,),
        )

        cursor.execute(
            "UPDATE hint SET queue_position = queue_position - 1 WHERE status IN " + _HINT_ACTIVE_STATES + " AND queue_position > %s",
            (answered_pos,),
        )
        _promote_top_hint(cursor)
        conn.commit()
    except Exception as e:
        debug_log(1, "Error answering hint %d: %s" % (id, e))
        raise Exception(f"Exception answering hint {id}: {e}")

    invalidate_cache_with_stats()
    debug_log(3, "Hint %d answered, remaining hints promoted" % id)
    return {"status": "ok", "message": f"Hint {id} answered"}


@app.route("/hints/<int:id>/demote", endpoint="demotehint", methods=["POST"])
@swag_from("swag/demotehint.yaml", endpoint="demotehint", methods=["POST"])
def demote_hint(id):
    """Swap a hint with the one below it in the queue. Resets ready/submitted back to queued."""
    debug_log(4, "start with hint id: %d" % id)
    try:
        conn, cursor = _cursor()
        cursor.execute(
            "SELECT id, queue_position, status FROM hint WHERE id = %s AND status IN " + _HINT_ACTIVE_STATES,
            (id,),
        )
        hint = cursor.fetchone()
        if not hint:
            debug_log(3, "Hint %d not found or already answered" % id)
            return {"status": "error", "error": f"Hint {id} not found or already answered"}, 404

        current_pos = hint["queue_position"]

        cursor.execute(
            "SELECT id FROM hint WHERE status IN " + _HINT_ACTIVE_STATES + " AND queue_position = %s",
            (current_pos + 1,),
        )
        below = cursor.fetchone()
        if not below:
            debug_log(3, "Hint %d is already at the bottom of the queue" % id)
            return {"status": "error", "error": f"Hint {id} is already at the bottom of the queue"}, 400

        cursor.execute(
            "UPDATE hint SET queue_position = %s WHERE id = %s",
            (current_pos + 1, id),
        )
        cursor.execute(
            "UPDATE hint SET queue_position = %s WHERE id = %s",
            (current_pos, below["id"]),
        )
        # Reset demoted hint to queued (it's no longer at top)
        if hint["status"] in ("ready", "submitted"):
            cursor.execute(
                "UPDATE hint SET status = 'queued', submitted_at = NULL WHERE id = %s",
                (id,),
            )
        _promote_top_hint(cursor)
        conn.commit()
    except Exception as e:
        debug_log(1, "Error demoting hint %d: %s" % (id, e))
        raise Exception(f"Exception demoting hint {id}: {e}")

    invalidate_cache_with_stats()
    debug_log(3, "Hint %d demoted from position %d to %d" % (id, current_pos, current_pos + 1))
    return {"status": "ok", "message": f"Hint {id} demoted"}


@app.route("/hints/<int:id>/submit", endpoint="submithint", methods=["POST"])
@swag_from("swag/submithint.yaml", endpoint="submithint", methods=["POST"])
def submit_hint(id):
    """Mark a ready hint as submitted to HQ"""
    debug_log(4, "start with hint id: %d" % id)
    try:
        conn, cursor = _cursor()
        cursor.execute(
            "SELECT id, queue_position, status FROM hint WHERE id = %s AND status = 'ready'",
            (id,),
        )
        hint = cursor.fetchone()
        if not hint:
            debug_log(3, "Hint %d not found or not in 'ready' state" % id)
            return {"status": "error", "error": f"Hint {id} not found or not in 'ready' state"}, 404

        cursor.execute(
            "UPDATE hint SET status = 'submitted', submitted_at = NOW() WHERE id = %s",
            (id,),
        )
        conn.commit()
    except Exception as e:
        debug_log(1, "Error submitting hint %d: %s" % (id, e))
        raise Exception(f"Exception submitting hint {id}: {e}")

    invalidate_cache_with_stats()
    debug_log(3, "Hint %d submitted to HQ" % id)
    return {"status": "ok", "message": f"Hint {id} submitted to HQ"}


@app.route("/hints/<int:id>", endpoint="deletehint", methods=["DELETE"])
@swag_from("swag/deletehint.yaml", endpoint="deletehint", methods=["DELETE"])
def delete_hint(id):
    """Remove a hint request from the queue and reorder remaining"""
    debug_log(4, "start with hint id: %d" % id)
    try:
        conn, cursor = _cursor()
        cursor.execute(
            "SELECT id, queue_position, status FROM hint WHERE id = %s",
            (id,),
        )
        hint = cursor.fetchone()
        if not hint:
            debug_log(3, "Hint %d not found for deletion" % id)
            return {"status": "error", "error": f"Hint {id} not found"}, 404

        deleted_pos = hint["queue_position"]
        was_active = hint["status"] in ("queued", "ready", "submitted")

        cursor.execute("DELETE FROM hint WHERE id = %s", (id,))

        if was_active and deleted_pos > 0:
            cursor.execute(
                "UPDATE hint SET queue_position = queue_position - 1 WHERE status IN " + _HINT_ACTIVE_STATES + " AND queue_position > %s",
                (deleted_pos,),
            )
        _promote_top_hint(cursor)
        conn.commit()
    except Exception as e:
        debug_log(1, "Error deleting hint %d: %s" % (id, e))
        raise Exception(f"Exception deleting hint {id}: {e}")

    invalidate_cache_with_stats()
    debug_log(3, "Hint %d deleted" % id)
    return {"status": "ok", "message": f"Hint {id} deleted"}


if __name__ == "__main__":
    if initdrive() != 0:
        debug_log(0, "Startup google drive initialization failed.")
        sys.exit(255)
    else:
        debug_log(
            3,
            "Authenticated to google drive. Existing drive folder %s found with id %s."
            % (configstruct["HUNT_FOLDER_NAME"], pblib.huntfolderid),
        )
    app.run()
