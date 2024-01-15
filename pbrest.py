import MySQLdb
import sys
import flasgger
import pblib
import traceback
from flask import Flask, request
from flask_restful import Api
from flask_mysqldb import MySQL
from pblib import *
from pbgooglelib import *
from pbdiscordlib import *
from pandas.core.dtypes.generic import ABCIntervalIndex
from secrets import token_hex
from flasgger.utils import swag_from
from pbldaplib import *
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
app.config["MYSQL_HOST"] = config["MYSQL"]["HOST"]
app.config["MYSQL_USER"] = config["MYSQL"]["USERNAME"]
app.config["MYSQL_PASSWORD"] = config["MYSQL"]["PASSWORD"]
app.config["MYSQL_DB"] = config["MYSQL"]["DATABASE"]
app.config["MYSQL_CURSORCLASS"] = "DictCursor"
mysql = MySQL(app)
api = Api(app)
swagger = flasgger.Swagger(app)


@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    errmsg = str(e)
    debug_log(0, errmsg)
    return {"error": str(e)}, code


# GET/READ Operations


@app.route("/all", endpoint="all", methods=["GET"])
# @swag_from("swag/getall.yaml", endpoint="all", methods=["GET"])
def get_all_all():
    debug_log(4, "start")
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        cursor.execute("SELECT * from puzzle_view")
        puzzle_view = cursor.fetchall()
    except:
        raise Exception("Exception in querying puzzle_view")

    all_puzzles = {}
    for puzzle in puzzle_view:
        all_puzzles[puzzle["id"]] = puzzle

    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        cursor.execute("SELECT * from round_view")
        round_view = cursor.fetchall()
    except:
        raise Exception("Exception in querying round_view")

    def is_int(val):
        try:
            int(val)
            return True
        except:
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

    return {"rounds": rounds}


@app.route("/puzzles", endpoint="puzzles", methods=["GET"])
@swag_from("swag/getpuzzles.yaml", endpoint="puzzles", methods=["GET"])
def get_all_puzzles():
    debug_log(4, "start")
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT id, name from puzzle")
        puzzlist = cursor.fetchall()
    except IndexError:
        raise Exception("Exception in fetching all puzzles from database")

    debug_log(4, "listed all puzzles")
    return {
        "status": "ok",
        "puzzles": puzzlist,
    }


@app.route("/puzzles/<id>", endpoint="puzzle_id", methods=["GET"])
@swag_from("swag/getpuzzleid.yaml", endpoint="puzzle_id", methods=["GET"])
def get_one_puzzle(id):
    debug_log(4, "start. id: %s" % id)
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        cursor.execute("SELECT * from puzzle_view where id = %s", (id,))
        puzzle = cursor.fetchone()
    except IndexError:
        raise Exception("Puzzle %s not found in database" % id)
    except:
        raise Exception("Exception in fetching puzzle %s from database" % id)

    debug_log(5, "fetched puzzle %s: %s" % (id, puzzle))
    return {
        "status": "ok",
        "puzzle": puzzle,
    }


@app.route("/puzzles/<id>/<part>", endpoint="puzzle_part", methods=["GET"])
@swag_from("swag/getpuzzlepart.yaml", endpoint="puzzle_part", methods=["GET"])
def get_puzzle_part(id, part):
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    if part == "lastact":
        rv = get_last_activity_for_puzzle(id)
    else:
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
            cursor.execute(
                f"SELECT {part} from puzzle_view where id = %s LIMIT 1", (id,)
            )
            rv = cursor.fetchone()[part]
        except TypeError:
            raise Exception("Puzzle %s not found in database" % id)
        except:
            raise Exception(
                "Exception in fetching %s part for puzzle %s from database"
                % (
                    part,
                    id,
                )
            )

    debug_log(4, "fetched puzzle part %s for %s" % (part, id))
    return {"status": "ok", "puzzle": {"id": id, part: rv}}


@app.route("/rounds", endpoint="rounds", methods=["GET"])
@swag_from("swag/getrounds.yaml", endpoint="rounds", methods=["GET"])
def get_all_rounds():
    debug_log(4, "start")
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT id, name from round")
        roundlist = cursor.fetchall()
    except:
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
    rounds = get_all_all()["rounds"]
    round = next((round for round in rounds if str(round["id"]) == str(id)), None)
    if not round:
        raise Exception("Round %s not found in database" % id)

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
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(f"SELECT {part} from round_view where id = %s", (id,))
        answer = cursor.fetchone()[part]
    except TypeError:
        raise Exception("Round %s not found in database" % id)
    except:
        raise Exception(
            "Exception in fetching %s part for round %s from database" % (part, id)
        )

    if part == "puzzles":
        answer = get_puzzles_from_list(answer)

    debug_log(4, "fetched round part %s for %s" % (part, id))
    return {"status": "ok", "round": {"id": id, part: answer}}


@app.route("/solvers", endpoint="solvers", methods=["GET"])
@swag_from("swag/getsolvers.yaml", endpoint="solvers", methods=["GET"])
def get_all_solvers():
    result = {}
    debug_log(4, "start")
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT id, name from solver")
        solvers = cursor.fetchall()
    except:
        raise Exception("Exception in fetching all solvers from database")

    debug_log(4, "listed all solvers")
    return {"status": "ok", "solvers": solvers}


@app.route("/solvers/<id>", endpoint="solver_id", methods=["GET"])
@swag_from("swag/getsolverid.yaml", endpoint="solver_id", methods=["GET"])
def get_one_solver(id):
    debug_log(4, "start. id: %s" % id)
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        cursor.execute("SELECT * from solver_view where id = %s", (id,))
        solver = cursor.fetchone()
    except IndexError:
        raise Exception("Solver %s not found in database" % id)
    except:
        raise Exception("Exception in fetching solver %s from database" % id)

    solver["lastact"] = get_last_activity_for_solver(id)
    debug_log(4, "fetched solver %s" % id)
    return {
        "status": "ok",
        "solver": solver,
    }


@app.route("/solvers/<id>/<part>", endpoint="solver_part", methods=["GET"])
@swag_from("swag/getsolverpart.yaml", endpoint="solver_part", methods=["GET"])
def get_solver_part(id, part):
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    if part == "lastact":
        rv = get_last_activity_for_solver(id)
    else:
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
            cursor.execute(f"SELECT {part} from solver_view where id = %s", (id,))
            rv = cursor.fetchone()[part]
        except TypeError:
            raise Exception("Solver %s not found in database" % id)
        except:
            raise Exception(
                "Exception in fetching %s part for solver %s from database"
                % (
                    part,
                    id,
                )
            )

    debug_log(4, "fetched round part %s for %s" % (part, id))
    return {"status": "ok", "solver": {"id": id, part: rv}}


@app.route("/version", endpoint="version", methods=["GET"])
@swag_from("swag/getversion.yaml", endpoint="version", methods=["GET"])
def get_current_version():
    debug_log(4, "start")
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(version) AS max_version from log")
        rv = cursor.fetchone()["max_version"]
    except:
        raise Exception("Exception in fetching latest version from database")

    debug_log(5, "fetched latest version number: %s from database" % str(rv))
    return {"status": "ok", "version": rv}


@app.route("/version/<fromver>/<tover>", endpoint="version_diff", methods=["GET"])
@swag_from("swag/getversiondiff.yaml", endpoint="version_diff", methods=["GET"])
def get_diff(fromver, tover):
    debug_log(4, "start. fromver: %s, tover: %s" % (fromver, tover))

    if fromver > tover:
        raise Exception("Version numbers being compared must be in order.")

    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT * FROM log WHERE version >= %s AND version <= %s",
            (fromver, tover),
        )
        versionlist = cursor.fetchall()
    except TypeError:
        raise Exception(
            "Exception fetching version diff from %s to %s from database"
            % (
                fromver,
                tover,
            )
        )

    debug_log(5, "fetched version diff from %s to %s" % (fromver, tover))
    return {"status": "ok", "versions": versionlist}


@app.route("/version/diff", endpoint="version_fulldiff", methods=["GET"])
@swag_from("swag/getversionfulldiff.yaml", endpoint="version_fulldiff", methods=["GET"])
def get_full_diff():
    debug_log(4, "start")
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT * FROM log")
        versionlist = cursor.fetchall()
    except TypeError:
        raise Exception("Exception fetching all-time version diff from database")

    debug_log(5, "fetched all-time version diff")
    return {"status": "ok", "versions": versionlist}


@app.route("/config", endpoint="config", methods=["GET"])
# @swag_from("swag/getconfig.yaml", endpoint="config", methods=["GET"])
def get_config():
    debug_log(4, "start")
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM config")
        config = {row["key"]: row["val"] for row in cursor.fetchall()}
    except TypeError:
        raise Exception("Exception fetching config info from database")

    debug_log(5, "fetched all-time version diff")
    return {"status": "ok", "config": config}


# POST/WRITE Operations


@app.route("/puzzles", endpoint="post_puzzles", methods=["POST"])
@swag_from("swag/putpuzzle.yaml", endpoint="post_puzzles", methods=["POST"])
def create_puzzle():
    debug_log(4, "start")
    try:
        data = request.get_json()
        puzname = sanitize_string(data["name"])
        puzuri = bleach.clean(data["puzzle_uri"])
        roundid = int(data["round_id"])
        debug_log(5, "request data is - %s" % str(data))
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception(
            "One or more expected fields (name, puzzle_uri, round_id) missing."
        )

    # Check for duplicate
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM puzzle WHERE name = %s LIMIT 1", (puzname,))
        existing_puzzle = cursor.fetchone()
    except:
        raise Exception(
            "Exception checking database for duplicate puzzle before insert"
        )

    if existing_puzzle:
        raise Exception("Duplicate puzzle name %s detected" % puzname)

    # Get round drive link and name
    round_drive_uri = get_round_part(roundid, "drive_uri")["round"]["drive_uri"]
    round_name = get_round_part(roundid, "name")["round"]["name"]
    round_drive_id = round_drive_uri.split("/")[-1]

    # Make new channel so we can get channel id and link (use doc redirect hack since no doc yet)
    drive_uri = "%s/doc.php?pname=%s" % (config["APP"]["BIN_URI"], puzname)
    chat_channel = chat_create_channel_for_puzzle(
        puzname, round_name, puzuri, drive_uri
    )
    debug_log(4, "return from creating chat channel: %s" % str(chat_channel))

    try:
        chat_id = chat_channel[0]
        chat_link = chat_channel[1]
    except:
        raise Exception("Error in creating chat channel for puzzle")

    debug_log(4, "chat channel for puzzle %s is made" % puzname)

    # Create google sheet
    drive_id = create_puzzle_sheet(
        round_drive_id,
        {
            "name": puzname,
            "roundname": round_name,
            "puzzle_uri": puzuri,
            "chat_uri": chat_link,
        },
    )
    drive_uri = "https://docs.google.com/spreadsheets/d/%s/edit#gid=1" % drive_id
    drive_link = '<a href="%s">%s</a>' % (drive_uri, puzname)

    # Actually insert into the database
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO puzzle
            (name, puzzle_uri, round_id, chat_channel_id, chat_channel_link, chat_channel_name, drive_id, drive_uri, drive_link)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                puzname,
                puzuri,
                roundid,
                chat_id,
                chat_link,
                puzname.lower(),
                drive_id,
                drive_uri,
                drive_link,
            ),
        )
        conn.commit()
    except MySQLdb._exceptions.IntegrityError:
        raise Exception(
            "MySQL integrity failure. Does another puzzle with the same name %s exist?"
            % puzname
        )
    except:
        raise Exception("Exception in insertion of puzzle %s into database" % puzname)

    # We need to figure out what the ID is that the puzzle got assigned
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM puzzle WHERE name = %s", (puzname,))
        puzzle = cursor.fetchone()
        myid = str(puzzle["id"])
    except:
        raise Exception("Exception checking database for puzzle after insert")

    # Announce new puzzle in chat
    chat_announce_new(puzname)

    debug_log(
        3,
        "puzzle %s added to system fully (chat room, spreadsheet, database, etc.)!"
        % puzname,
    )

    return {
        "status": "ok",
        "puzzle": {
            "id": myid,
            "name": puzname,
            "chat_channel_id": chat_id,
            "chat_link": chat_link,
            "drive_uri": drive_uri,
        },
    }


@app.route("/rounds", endpoint="post_rounds", methods=["POST"])
@swag_from("swag/putround.yaml", endpoint="post_rounds", methods=["POST"])
def create_round():
    debug_log(4, "start")
    try:
        data = request.get_json()
        roundname = sanitize_string(data["name"])
        debug_log(5, "request data is - %s" % str(data))
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception("Expected field (name) missing.")

    if not roundname or roundname == "":
        raise Exception("Round with empty name disallowed")

    # Check for duplicate
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM round WHERE name = %s LIMIT 1", (roundname,))
        existing_round = cursor.fetchone()
    except:
        raise Exception("Exception checking database for duplicate round before insert")

    if existing_round:
        raise Exception("Duplicate round name %s detected" % roundname)

    chat_status = chat_announce_round(roundname)
    debug_log(4, "return from announcing round in chat is - %s" % str(chat_status))

    if chat_status == None:
        raise Exception("Error in announcing new round in chat")

    debug_log(4, "Making call to create google drive folder for round")
    round_drive_id = create_round_folder(roundname)
    round_drive_uri = "https://drive.google.com/drive/u/1/folders/%s" % round_drive_id
    debug_log(5, "Round drive URI created: %s" % round_drive_uri)
    # Actually insert into the database
    # try:
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO round (name, drive_uri) VALUES (%s, %s)",
        (roundname, round_drive_uri),
    )
    conn.commit()
    # except:
    #     raise Exception("Exception in insertion of round %s into database" % roundname)

    debug_log(
        3, "round %s added to database! drive_uri: %s" % (roundname, round_drive_uri)
    )

    return {"status": "ok", "round": {"name": roundname}}


@app.route("/rounds/<id>/<part>", endpoint="post_round_part", methods=["POST"])
@swag_from("swag/putroundpart.yaml", endpoint="post_round_part", methods=["POST"])
def update_round_part(id, part):
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    try:
        data = request.get_json()
        value = data[part]
        if value == "NULL":
            value = None
        debug_log(5, "request data is - %s" % str(data))
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception("Expected field (%s) missing." % part)

    # Actually insert into the database
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(f"UPDATE round SET {part} = %s WHERE id = %s", (value, id))
        conn.commit()
    except KeyError:
        raise Exception(
            "Exception in modifying %s of round %s into database" % (part, id)
        )

    debug_log(3, "round %s %s updated to %s" % (id, part, value))

    return {"status": "ok", "round": {"id": id, part: value}}


@app.route("/solvers", endpoint="post_solver", methods=["POST"])
@swag_from("swag/putsolver.yaml", endpoint="post_solver", methods=["POST"])
def create_solver():
    debug_log(4, "start")
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
        name = sanitize_string(data["name"])
        fullname = data["fullname"]
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception("One or more expected fields (name, fullname) missing.")

    # Actually insert into the database
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO solver (name, fullname) VALUES (%s, %s)", (name, fullname)
        )
        conn.commit()
    except MySQLdb._exceptions.IntegrityError:
        raise Exception(
            "MySQL integrity failure. Does another solver with the same name %s exist?"
            % name
        )
    except:
        raise Exception("Exception in insertion of solver %s into database" % name)

    debug_log(3, "solver %s added to database!" % name)

    return {"status": "ok", "solver": {"name": name, "fullname": fullname}}


@app.route("/solvers/<id>/<part>", endpoint="post_solver_part", methods=["POST"])
@swag_from("swag/putsolverpart.yaml", endpoint="post_solver_part", methods=["POST"])
def update_solver_part(id, part):
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
        value = data[part]
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception("Expected %s field missing" % part)
    # Check if this is a legit solver
    mysolver = get_one_solver(id)
    debug_log(5, "return value from get_one_solver %s is %s" % (id, mysolver))
    if "status" not in mysolver or mysolver["status"] != "ok":
        raise Exception("Error looking up solver %s" % id)

    # This is a change to the solver's claimed puzzle
    if part == "puzz":
        if value:
            # Assigning puzzle, so check if puzzle is real
            debug_log(4, "trying to assign solver %s to puzzle %s" % (id, value))
            mypuzz = get_one_puzzle(value)
            debug_log(5, "return value from get_one_puzzle %s is %s" % (value, mypuzz))
            if mypuzz["status"] != "ok":
                raise Exception(
                    "Error retrieving info on puzzle %s, which user %s is attempting to claim"
                    % (value, id)
                )
            # Since we're assigning, the puzzle should automatically transit out of "NEW" state if it's there
            if mypuzz["puzzle"]["status"] == "New":
                debug_log(
                    3,
                    "Automatically marking puzzle id %s, name %s as being worked on."
                    % (mypuzz["puzzle"]["id"], mypuzz["puzzle"]["name"]),
                )
                update_puzzle_part_in_db(value, "status", "Being worked")

        else:
            # Puzz is empty, so this is a de-assignment. Populate the db with empty string for it.
            value = None

        # Now log it in the activity table
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO activity
                (puzzle_id, solver_id, source, type)
                VALUES (%s, %s, 'apache', 'interact')
                """,
                (value, id),
            )
            conn.commit()
        except TypeError:
            raise Exception(
                "Exception in logging change to puzzle %s in activity table for solver %s in database"
                % (value, id)
            )

        debug_log(4, "Activity table updated: solver %s taking puzzle %s" % (id, value))

        if mypuzz["puzzle"]["status"] != "Solved":
            # Now actually assign puzzle to solver on unsolved puzzles
            try:
                conn = mysql.connection
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO puzzle_solver (puzzle_id, solver_id) VALUES (%s, %s)",
                    (value, id),
                )
                conn.commit()
            except Exception:
                tb = traceback.format_exc()
                raise Exception(
                    "Exception in setting solver to %s for puzzle %s. Traceback: %s"
                    % (id, value, tb)
                )

            debug_log(3, "Solver %s claims to be working on %s" % (id, value))

        return {"status": "ok", "solver": {"id": id, part: value}}

    # This is actually a change to the solver's info
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(f"UPDATE solver SET {part} = %s WHERE id = %s", (value, id))
        conn.commit()
    except:
        raise Exception(
            "Exception in modifying %s of solver %s in database" % (part, id)
        )

    debug_log(3, "solver %s %s updated in database" % (id, part))

    return {"status": "ok", "solver": {"id": id, part: value}}


@app.route("/puzzles/<id>/<part>", endpoint="post_puzzle_part", methods=["POST"])
@swag_from("swag/putpuzzlepart.yaml", endpoint="post_puzzle_part", methods=["POST"])
def update_puzzle_part(id, part):
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
        value = data[part]
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception("Expected %s field missing" % part)

    # Check if this is a legit puzzle
    mypuzzle = get_one_puzzle(id)
    debug_log(5, "return value from get_one_puzzle %s is %s" % (id, mypuzzle))
    if "status" not in mypuzzle or mypuzzle["status"] != "ok":
        raise Exception("Error looking up puzzle %s" % id)

    if part == "lastact":
        set_new_activity_for_puzzle(id, value)

    elif part == "status":
        debug_log(4, "part to update is status")
        if value == "Solved":
            if mypuzzle["puzzle"]["status"] == "Solved":
                raise Exception(
                    "Puzzle %s is already solved! Refusing to re-solve." % id
                )
            # Don't mark puzzle as solved if there is no answer filled in
            if not mypuzzle["puzzle"]["answer"]:
                raise Exception(
                    "Puzzle %s has no answer! Refusing to mark as solved." % id
                )
            else:
                debug_log(
                    3,
                    "Puzzle id %s name %s has been Solved!!!"
                    % (id, mypuzzle["puzzle"]["name"]),
                )
                clear_puzzle_solvers(id)
                update_puzzle_part_in_db(id, part, value)
                chat_announce_solved(mypuzzle["puzzle"]["name"])
        elif (
            value == "Needs eyes"
            or value == "Critical"
            or value == "Unnecessary"
            or value == "WTF"
            or value == "Being worked"
        ):
            update_puzzle_part_in_db(id, part, value)
            chat_announce_attention(mypuzzle["puzzle"]["name"])

    elif part == "xyzloc":
        update_puzzle_part_in_db(id, part, value)
        if (value != None) and (value != ""):
            chat_say_something(
                mypuzzle["puzzle"]["chat_channel_id"],
                "**ATTENTION:** %s is being worked on at %s"
                % (mypuzzle["puzzle"]["name"], value),
            )
        else:
            debug_log(3, "puzzle xyzloc removed. skipping discord announcement")

    elif part == "answer":
        if data != "" and data != None:
            # Mark puzzle as solved automatically when answer is filled in
            update_puzzle_part_in_db(id, "status", "Solved")
            value = value.upper()
            update_puzzle_part_in_db(id, part, value)
            debug_log(
                3,
                "Puzzle id %s name %s has been Solved!!!"
                % (id, mypuzzle["puzzle"]["name"]),
            )
            clear_puzzle_solvers(id)
            chat_announce_solved(mypuzzle["puzzle"]["name"])

    elif part == "comments":
        update_puzzle_part_in_db(id, part, value)
        chat_say_something(
            mypuzzle["puzzle"]["chat_channel_id"],
            "**ATTENTION** new comment for puzzle %s: %s"
            % (mypuzzle["puzzle"]["name"], value),
        )

    elif part == "round":
        update_puzzle_part_in_db(id, part, value)
        # This obviously needs some sanity checking

    else:
        raise Exception("Invalid part name %s" % part)

    debug_log(
        3,
        "puzzle name %s, id %s, part %s has been set to %s"
        % (mypuzzle["puzzle"]["name"], id, part, value),
    )

    return {"status": "ok", "puzzle": {"id": id, part: value}}


@app.route("/account", endpoint="post_new_account", methods=["POST"])
@swag_from("swag/putnewaccount.yaml", endpoint="post_new_account", methods=["POST"])
def new_account():
    debug_log(4, "start.")
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
        username = data["username"]
        fullname = data["fullname"]
        email = data["email"]
        password = data["password"]
        reset = data.get("reset")
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception(
            "Expected field missing (username, fullname, email, or password)"
        )

    allusers = get_all_solvers()["solvers"]
    userfound = False
    for solver in allusers:
        if solver["name"] == username:
            if reset == "reset":
                userfound = True
                debug_log(3, "Password reset attempt detected for user %s" % username)
            else:
                raise Exception(
                    "Username %s already exists. Pick another, or add reset flag."
                    % username
                )

    if reset == "reset":
        if not userfound:
            raise Exception("Username %s not found in system to reset." % username)
        if verify_email_for_user(email, username) != 1:
            raise Exception(
                "Username %s does not match email %s in the system."
                % (
                    username,
                    email,
                )
            )

    # Generate the code
    code = token_hex(4)
    debug_log(4, "code picked: %s" % code)

    # Actually insert into the database
    try:
        conn = mysql.connection
        cursor = conn.cursor()
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
            "Exception in insertion of unverified user request %s into database"
            % username
        )

    if email_user_verification(email, code, fullname, username) == "OK":
        debug_log(
            3,
            "unverified new user %s added to database with verification code %s. email sent."
            % (username, code),
        )
        return {"status": "ok", "code": code}

    raise Exception("some error emailing code to user")


@app.route("/finishaccount/<code>", endpoint="get_finish_account", methods=["GET"])
@swag_from("swag/getfinishaccount.yaml", endpoint="get_finish_account", methods=["GET"])
def finish_account(code):
    debug_log(4, "start. code %s" % code)

    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT username, fullname, email, password
            FROM newuser
            WHERE code = %s
            """,
            (code,),
        )
        newuser = cursor.fetchone()

        debug_log(5, "query return: %s" % str(newuser))

        username = newuser["username"]
        fullname = newuser["fullname"]
        email = newuser["email"]
        password = newuser["password"]

    except TypeError:
        raise Exception("Code %s is not valid." % code)

    debug_log(
        4,
        "valid code. username: %s fullname: %s email: %s password: REDACTED"
        % (username, fullname, email),
    )

    firstname, lastname = fullname.split(maxsplit=1)

    retcode = add_or_update_user(username, firstname, lastname, email, password)

    if retcode == "OK":
        # Delete code and preliminary entry now
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("""DELETE FROM newuser WHERE code = %s""", (code,))
        conn.commit()
        return {"status": "ok"}

    raise Exception(retcode)


@app.route("/deleteuser/<username>", endpoint="get_delete_account", methods=["GET"])
@swag_from("swag/getdeleteaccount.yaml", endpoint="get_delete_account", methods=["GET"])
def delete_account(username):
    debug_log(4, "start. code %s" % username)

    delete_pb_solver(username)
    debug_log(3, "user %s deleted from solver db" % username)

    errmsg = delete_user(username)

    if errmsg != "OK":
        raise Exception(errmsg)

    return {"status": "ok"}


############### END REST calls section


def unassign_solver_by_name(name):
    debug_log(4, "start, called with (name): %s" % name)

    # We have to look up the solver id for the given name first.
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM solver WHERE name = %s LIMIT 1", (name,))
    id = cursor.fetchone()["id"]
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO puzzle_solver (puzzle_id, solver_id) VALUES (NULL, %s)", (id,)
    )
    conn.commit()

    debug_log(3, "Solver id: %s, name: %s unassigned" % (id, name))

    return 0


def clear_puzzle_solvers(id):
    debug_log(4, "start, called with (id): %s" % id)

    mypuzzle = get_one_puzzle(id)
    if mypuzzle["puzzle"]["cursolvers"]:
        mypuzzlesolvers = mypuzzle["puzzle"]["cursolvers"]
        solverslist = mypuzzlesolvers.split(",")
        debug_log(
            4, "found these solvers to clear from puzzle %s: %s" % (id, solverslist)
        )

        for solver in solverslist:
            unassign_solver_by_name(solver)

    else:
        debug_log(4, "no solvers found on puzzle %s" % id)

    return 0


def update_puzzle_part_in_db(id, part, value):
    debug_log(4, "start, called with (id, part, value): %s, %s, %s" % (id, part, value))
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute(f"UPDATE puzzle SET {part} = %s WHERE id = %s", (value, id))
    conn.commit()

    debug_log(4, "puzzle %s %s updated in database" % (id, part))

    return 0


def get_puzzles_from_list(list):
    debug_log(4, "start, called with: %s" % list)
    if not list:
        return []

    puzlist = list.split(",")
    conn = mysql.connection
    puzarray = []
    for mypuz in puzlist:
        debug_log(4, "fetching puzzle info for pid: %s" % mypuz)
        puzarray.append(get_one_puzzle(mypuz)["puzzle"])

    debug_log(4, "puzzle list assembled is: %s" % puzarray)
    return puzarray


def get_last_activity_for_puzzle(id):
    debug_log(4, "start, called with: %s" % id)
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        cursor.execute(
            """SELECT * from activity where puzzle_id = %s ORDER BY time DESC LIMIT 1""",
            (id,),
        )
        return cursor.fetchone()
    except IndexError:
        debug_log(4, "No Activity for Puzzle %s found in database yet" % id)
        return None


def get_last_activity_for_solver(id):
    debug_log(4, "start, called with: %s" % id)
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
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
        puzzle_id = id
        source = actstruct["source"]
        type = actstruct["type"]
    except:
        debug_log(
            0,
            "Failure parsing activity dict. Needs solver_id, source, type. dict passed in is: %s"
            % actstruct,
        )
        return 255

    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO activity
            (puzzle_id, solver_id, source, type)
            VALUES (%s, %s, %s, %s)
            """,
            (puzzle_id, solver_id, source, type),
        )
        conn.commit()
    except TypeError:
        debug_log(
            0,
            "Exception in logging change to puzzle %s in activity table for solver %s in database"
            % (value, id),
        )
        return 255

    debug_log(3, "Updated activity for puzzle id %s" % (puzzle_id))
    return 0


def delete_pb_solver(username):
    debug_log(4, "start, called with username %s" % username)

    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute("DELETE from solver where name = %s", (username,))
    conn.commit()
    return 0


if __name__ == "__main__":
    if initdrive() != 0:
        debug_log(0, "Startup google drive initialization failed.")
        sys.exit(255)
    else:
        debug_log(
            3,
            "Authenticated to google drive. Existing drive folder %s found with id %s."
            % (config["GOOGLE"]["HUNT_FOLDER_NAME"], pblib.huntfolderid),
        )
    app.run()
