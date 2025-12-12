import MySQLdb
import sys
import flasgger
import pblib
import traceback
import yaml
import inspect
import datetime
import bleach
import smtplib
from flask import Flask, request, jsonify
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
import json
import datetime
import re

app = Flask(__name__)
app.config["MYSQL_HOST"] = config["MYSQL"]["HOST"]
app.config["MYSQL_USER"] = config["MYSQL"]["USERNAME"]
app.config["MYSQL_PASSWORD"] = config["MYSQL"]["PASSWORD"]
app.config["MYSQL_DB"] = config["MYSQL"]["DATABASE"]
app.config["MYSQL_CURSORCLASS"] = "DictCursor"
app.config["MYSQL_CHARSET"] = "utf8mb4"
mysql = MySQL(app)
api = Api(app)
swagger = flasgger.Swagger(app)

@app.errorhandler(Exception)
def handle_error(e):
    code = 500
    if isinstance(e, HTTPException):
        code = e.code
    
    error_details = {
        "error": str(e),
        "error_type": e.__class__.__name__,
        "traceback": traceback.format_exc()
    }
    
    debug_log(0, f"Error occurred: {error_details}")
    return error_details, code


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

@app.route("/rbac/<priv>/<uid>", endpoint="rbac_priv_uid", methods=["GET"])
@swag_from("swag/getrbacprivuid.yaml", endpoint="rbac_priv_uid", methods=["GET"])
def check_priv(priv,uid):
    debug_log(4, "start. priv: %s, uid: %s" % (priv, uid))
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM privs WHERE uid = %s", (uid, )) 
        rv = cursor.fetchone()
    except:
        raise Exception("Exception querying database for privs)")

    debug_log(3, "in database user %s ACL is %s" % (uid, rv))

    if rv == None:
        return {
            "status": "ok",
            "allowed": False,
        }

    try:
        privanswer = rv[priv]
    except:
        raise Exception(
                "Exception in reading priv %s from user %s ACL. No such priv?"
                % (
                    priv,
                    uid,
                  )
                )

    if privanswer == "YES":
        return {
            "status": "ok",
            "allowed": True,
        }
    else:
        return {
            "status": "ok",
            "allowed": False,
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
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.id, r.name, r.round_uri, r.drive_uri, r.drive_id, r.status, r.comments,
                   GROUP_CONCAT(p.id) as puzzles
            FROM round r
            LEFT JOIN puzzle p ON p.round_id = r.id
            WHERE r.id = %s
            GROUP BY r.id
        """, (id,))
        round = cursor.fetchone()
        if not round:
            raise Exception("Round %s not found in database" % id)
            
        # Convert puzzles string to list of puzzle objects
        puzzle_ids = round['puzzles'].split(',') if round['puzzles'] else []
        puzzles = []
        for pid in puzzle_ids:
            if pid:  # Skip empty strings
                puzzles.append(get_one_puzzle(pid)['puzzle'])
        round['puzzles'] = puzzles
    except:
        raise Exception("Exception in fetching round %s from database" % id)

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
        # Use round table directly instead of round_view to get status
        cursor.execute(f"SELECT {part} from round where id = %s", (id,))
        answer = cursor.fetchone()
        if not answer:
            raise Exception("Round %s not found in database" % id)
        answer = answer[part]
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
        if solver is None:
            raise Exception("Solver %s not found in database" % id)
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

            # Assign the solver to the puzzle using the new JSON-based system
            assign_solver_to_puzzle(value, id)
        else:
            # Puzz is empty, so this is a de-assignment
            # Find the puzzle the solver is currently assigned to
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM puzzle 
                WHERE JSON_CONTAINS(current_solvers, 
                    JSON_OBJECT('solver_id', %s), 
                    '$.solvers'
                )
            """, (id,))
            current_puzzle = cursor.fetchone()
            if current_puzzle:
                # Unassign the solver from their current puzzle
                unassign_solver_from_puzzle(current_puzzle['id'], id)

        # Now log it in the activity table
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            # Get the source from the request data if provided, otherwise use default
            source = data.get('source', 'puzzleboss')
            cursor.execute(
                """
                INSERT INTO activity
                (puzzle_id, solver_id, source, type)
                VALUES (%s, %s, %s, 'interact')
                """,
                (value, id, source),
            )
            conn.commit()
        except TypeError:
            raise Exception(
                "Exception in logging change to puzzle %s in activity table for solver %s in database"
                % (value, id)
            )

        debug_log(4, "Activity table updated: solver %s taking puzzle %s" % (id, value))
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


@app.route("/config", endpoint="getconfig", methods=["GET"])
# @swag_from("swag/getconfig.yaml", endpoint="getconfig", methods=["GET"])
def get_config():
    debug_log(4, "start")
    try:
        conn = mysql.connection
        cursor = conn.cursor()
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
        debug_log(3, "Config change attempt.  struct: %s key %s val %s" % (str(data), mykey, myval))
    except Exception as e:
        raise Exception("Exception Interpreting input data for config change: %s" % e)
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO config (`key`, `val`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `key`=%s, `val`=%s", (mykey, myval, mykey, myval)
    )
    conn.commit()

    debug_log(2, "Config value %s changed successfully" % mykey)
    return {"status": "ok"}


@app.route("/botstats", endpoint="getbotstats", methods=["GET"])
def get_botstats():
    """Get all bot statistics"""
    debug_log(4, "start")
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT `key`, `val`, `updated` FROM botstats")
        rows = cursor.fetchall()
        botstats = {}
        for row in rows:
            botstats[row["key"]] = {
                "val": row["val"],
                "updated": row["updated"].strftime("%Y-%m-%dT%H:%M:%SZ") if row["updated"] else None
            }
    except Exception as e:
        raise Exception("Exception fetching botstats from database: %s" % e)

    debug_log(5, "fetched all botstats from database")
    return {"status": "ok", "botstats": botstats}


@app.route("/botstats/<key>", endpoint="putbotstat", methods=["POST"])
def put_botstat(key):
    """Update a single bot statistic"""
    debug_log(4, "start with key: %s" % key)
    try:
        data = request.get_json()
        myval = data["val"]
        debug_log(4, "Botstat update: key=%s val=%s" % (key, myval))
    except Exception as e:
        raise Exception("Exception interpreting input data for botstat update: %s" % e)
    
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO botstats (`key`, `val`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `val`=%s",
        (key, myval, myval)
    )
    conn.commit()

    debug_log(4, "Botstat %s updated successfully to %s" % (key, myval))
    return {"status": "ok"}


@app.route("/puzzles", endpoint="post_puzzles", methods=["POST"])
@swag_from("swag/putpuzzle.yaml", endpoint="post_puzzles", methods=["POST"])
def create_puzzle():
    try:
        puzzle_data = request.get_json()
        debug_log(5, f"Incoming puzzle creation payload: {json.dumps(puzzle_data, indent=2)}")
        if not puzzle_data or "puzzle" not in puzzle_data:
            return jsonify({"error": "Invalid JSON POST structure"}), 400
            
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
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM puzzle WHERE name = %s LIMIT 1", (name,))
        existing_puzzle = cursor.fetchone()
    except:
        raise Exception(
            "Exception checking database for duplicate puzzle before insert"
        )

    if existing_puzzle:
        raise Exception("Duplicate puzzle name %s detected" % name)

    # Get round drive link and name
    round_drive_uri = get_round_part(round_id, "drive_uri")["round"]["drive_uri"]
    round_name = get_round_part(round_id, "name")["round"]["name"]
    round_drive_id = round_drive_uri.split("/")[-1]

    # Make new channel so we can get channel id and link (use doc redirect hack since no doc yet)
    drive_uri = "%s/doc.php?pname=%s" % (configstruct["BIN_URI"], name)
    chat_channel = chat_create_channel_for_puzzle(
        name, round_name, puzzle_uri, drive_uri
    )
    debug_log(4, "return from creating chat channel: %s" % str(chat_channel))

    try:
        chat_id = chat_channel[0]
        chat_link = chat_channel[1]
    except:
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
    drive_uri = "https://docs.google.com/spreadsheets/d/%s/edit#gid=1" % drive_id

    # Actually insert into the database
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        
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
                name, # Store the full name with emojis intact
                drive_id,
                drive_uri,
                ismeta,
            ),
        )
        conn.commit()
    except MySQLdb._exceptions.IntegrityError:
        raise Exception(
            "MySQL integrity failure. Does another puzzle with the same name %s exist?"
            % name
        )
    except:
        raise Exception("Exception in insertion of puzzle %s into database" % name)

    # We need to figure out what the ID is that the puzzle got assigned
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM puzzle WHERE name = %s", (name,))
        puzzle = cursor.fetchone()
        myid = str(puzzle["id"])
        
        # Add activity entry for puzzle creation
        cursor.execute(
            """
            INSERT INTO activity
            (puzzle_id, solver_id, source, type)
            VALUES (%s, %s, 'puzzleboss', 'create')
            """,
            (myid, 100),
        )
        conn.commit()
    except:
        raise Exception("Exception checking database for puzzle after insert")

    # Announce new puzzle in chat
    chat_announce_new(name)

    debug_log(
        3,
        "puzzle %s added to system fully (chat room, spreadsheet, database, etc.)!"
        % name,
    )

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

@app.route("/rbac/<priv>/<uid>", endpoint="post_rbac_priv_uid", methods=["POST"])
@swag_from("swag/putrbacprivuid.yaml", endpoint="post_rbac_priv_uid", methods=["POST"])
def set_priv(priv,uid):
    debug_log(4, "start. priv: %s, uid %s" % (priv, uid))
    try:
        data = request.get_json()
        debug_log(4, "post data: %s" % (data))
        value = data["allowed"]
        if ( value != "YES" and value != "NO"):
            raise Exception("Improper privset allowed syntax. e.g. {'allowed':'YES'} or {'allowed':'NO'}")
    except Exception as e:
        raise Exception("Error interpreting privset JSON allowed field: %s" % (e))
    debug_log(3, "Attempting privset of uid %s:  %s = %s" % (uid, priv, value))

    # Actually insert into the database
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO privs (uid, {priv}) VALUES (%s, %s) ON DUPLICATE KEY UPDATE uid=%s, {priv}=%s", (uid, value, uid, value))
        conn.commit()
    except Exception as e:
        raise Exception("Error modifying priv table for uid %s priv %s value %s. Is priv string valid?" % (uid, priv, value))

    return {"status": "ok"}


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
        name = sanitize_puzzle_name(data["name"])
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


@app.route("/puzzles/<id>/<part>", endpoint="post_puzzle_part", methods=["POST"])
@swag_from("swag/putpuzzlepart.yaml", endpoint="post_puzzle_part", methods=["POST"])
def update_puzzle_part(id, part):
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
                
                # Check if this is a meta puzzle and if all metas in the round are solved
                if mypuzzle["puzzle"]["ismeta"]:
                    check_round_completion(mypuzzle["puzzle"]["round_id"])
        elif (
            value == "Needs eyes"
            or value == "Critical"
            or value == "Unnecessary"
            or value == "WTF"
            or value == "Being worked"
        ):
            update_puzzle_part_in_db(id, part, value)
            chat_announce_attention(mypuzzle["puzzle"]["name"])

    elif part == "ismeta":
        # When setting a puzzle as meta, just update it directly
        update_puzzle_part_in_db(id, part, value)
        
        # Check if this is a meta puzzle and if all metas in the round are solved
        if value:
            check_round_completion(mypuzzle["puzzle"]["round_id"])

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
            
            # Add activity entry for puzzle being solved
            try:
                conn = mysql.connection
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO activity
                    (puzzle_id, solver_id, source, type)
                    VALUES (%s, %s, 'puzzleboss', 'solve')
                    """,
                    (id, 100),
                )
                conn.commit()
            except:
                debug_log(1, "Exception in logging puzzle solve in activity table for puzzle %s" % id)
            
            # Check if this is a meta puzzle and if all metas in the round are solved
            if mypuzzle["puzzle"]["ismeta"]:
                check_round_completion(mypuzzle["puzzle"]["round_id"])

    elif part == "comments":
        update_puzzle_part_in_db(id, part, value)
        chat_say_something(
            mypuzzle["puzzle"]["chat_channel_id"],
            "**ATTENTION** new comment for puzzle %s: %s"
            % (mypuzzle["puzzle"]["name"], value),
        )
        
        # Add activity entry for comment
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO activity
                (puzzle_id, solver_id, source, type)
                VALUES (%s, %s, 'puzzleboss', 'comment')
                """,
                (id, 100),
            )
            conn.commit()
        except:
            debug_log(1, "Exception in logging comment in activity table for puzzle %s" % id)

    elif part == "round":
        update_puzzle_part_in_db(id, part, value)
        # This obviously needs some sanity checking

    elif part == "sheetcount":
        # Simple integer update for sheet count (set by bigjimmybot)
        update_puzzle_part_in_db(id, part, value)

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
    """
    Account creation endpoint with optional step parameter for progress tracking.
    
    Steps:
      1 - Validate code and return operation type (new/update)
      2 - Create/update Google account
      3 - Create/update LDAP entry
      4 - Add to solver DB (new accounts only, skipped for updates)
      5 - Cleanup (delete temporary newuser entry)
    
    If no step parameter, runs all steps at once (backward compatible).
    """
    step = request.args.get('step', None)
    debug_log(4, "start. code %s, step %s" % (code, step))

    # Always validate code and get user info first
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
    
    # For steps 2-5, accept operation from client (determined in step 1)
    # This prevents re-checking Google after step 2 already created the account
    operation_param = request.args.get('operation', None)
    
    if operation_param in ('new', 'update'):
        # Use client-provided operation (from step 1)
        operation = operation_param
        debug_log(4, "User %s: using client-provided operation '%s'" % (username, operation))
    else:
        # Step 1 or backward-compatible mode: determine operation from Google
        operation = "update" if verify_email_for_user(email, username) == 1 else "new"
        debug_log(4, "User %s: operation type is '%s' (new=create account, update=password reset)" % (username, operation))
    
    # If no step specified, run all steps (backward compatible)
    if step is None:
        debug_log(4, "User %s: Running all steps at once (no step parameter)" % username)
        retcode = add_or_update_user(username, firstname, lastname, email, password)
        if retcode == "OK":
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute("""DELETE FROM newuser WHERE code = %s""", (code,))
            conn.commit()
            debug_log(4, "User %s: All steps complete, temporary newuser entry deleted" % username)
            return {"status": "ok"}
        raise Exception(retcode)
    
    # Step 1: Just validate and return operation type
    if step == "1":
        debug_log(4, "User %s: Step 1 - Validation complete. Operation: %s" % (username, operation))
        return {
            "status": "ok",
            "step": 1,
            "operation": operation,
            "username": username
        }
    
    # Step 2: Google account
    if step == "2":
        if operation == "new":
            debug_log(4, "User %s: Step 2 - Creating new Google Workspace account" % username)
            result = add_user_to_google(username, firstname, lastname, password)
            if result != "OK":
                raise Exception("Failed to create Google account: %s" % result)
            debug_log(4, "User %s: Step 2 - Google Workspace account created successfully" % username)
            return {"status": "ok", "step": 2, "message": "Google account created"}
        else:
            debug_log(4, "User %s: Step 2 - Updating Google Workspace password" % username)
            result = change_google_user_password(username, password)
            if result != "OK":
                raise Exception("Failed to update Google password: %s" % result)
            debug_log(4, "User %s: Step 2 - Google Workspace password updated successfully" % username)
            return {"status": "ok", "step": 2, "message": "Google password updated"}
    
    # Step 3: LDAP
    if step == "3":
        if operation == "new":
            debug_log(4, "User %s: Step 3 - Creating new LDAP directory entry" % username)
        else:
            debug_log(4, "User %s: Step 3 - Updating password in LDAP directory" % username)
        retcode = create_or_update_ldap_user(username, firstname, lastname, email, password, operation)
        if retcode != "OK":
            raise Exception("Failed to update LDAP: %s" % retcode)
        if operation == "new":
            debug_log(4, "User %s: Step 3 - LDAP directory entry created successfully" % username)
            return {"status": "ok", "step": 3, "message": "LDAP account created"}
        else:
            debug_log(4, "User %s: Step 3 - LDAP password updated successfully" % username)
            return {"status": "ok", "step": 3, "message": "LDAP password updated"}
    
    # Step 4: Solver DB (new accounts only)
    # The solver DB tracks puzzle assignments and solver activity during the hunt
    # Check if solver already exists in DB (don't rely on LDAP check since step 3 just created the LDAP entry)
    if step == "4":
        debug_log(4, "User %s: Step 4 - Checking if solver already exists in Puzzleboss database" % username)
        solver_check = requests.get("%s/solvers/%s" % (config["API"]["APIURI"], username))
        solver_exists = solver_check.ok and solver_check.json().get("status") == "ok"
        
        if solver_exists:
            debug_log(4, "User %s: Step 4 - Solver already exists in database, skipping" % username)
            return {"status": "ok", "step": 4, "message": "Skipped (solver already exists)", "skipped": True}
        else:
            debug_log(4, "User %s: Step 4 - Adding to Puzzleboss solver database (for puzzle assignments)" % username)
            postbody = {"fullname": "%s %s" % (firstname, lastname), "name": username}
            solveraddresponse = requests.post(
                "%s/solvers" % config["API"]["APIURI"], json=postbody
            )
            if not solveraddresponse.ok:
                raise Exception("Failed to add to solver database")
            debug_log(4, "User %s: Step 4 - Added to solver database successfully" % username)
            return {"status": "ok", "step": 4, "message": "Added to solver database"}
    
    # Step 5: Cleanup
    # Delete the temporary newuser entry (contains verification code and password)
    if step == "5":
        debug_log(4, "User %s: Step 5 - Deleting temporary newuser entry from database" % username)
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("""DELETE FROM newuser WHERE code = %s""", (code,))
        conn.commit()
        debug_log(4, "User %s: Step 5 - Cleanup complete, account registration finished" % username)
        return {"status": "ok", "step": 5, "message": "Cleanup complete"}
    
    raise Exception("Invalid step: %s" % step)


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

@app.route("/deletepuzzle/<puzzlename>", endpoint="get_delete_puzzle", methods=["GET"])
@swag_from("swag/getdeletepuzzle.yaml", endpoint="get_delete_puzzle", methods=["GET"])
def delete_puzzle(puzzlename):
    debug_log(4, "start. delete puzzle named %s" % puzzlename)
    puzzid = get_puzzle_id_by_name(puzzlename)
    if puzzid == 0:
        debug_log(2, "puzzle named %s not found in system!" % puzzlename)
        raise Exception("puzzle not found in system.")
    sheetid = get_puzzle_part(puzzid, "drive_id")["puzzle"]["drive_id"]

    if delete_puzzle_sheet(sheetid) != 0:
        debug_log(2, "Puzzle id %s deletion request but sheet deletion failed! continuing. this may cause a mess!" % puzzid)

    clear_puzzle_solvers(puzzid)

    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("DELETE from puzzle where id = %s", (puzzid,))
        conn.commit()
    except:
        raise Exception("Puzzle deletion attempt for id %s name %s failed in database operation." % puzzid, puzzlename)

    debug_log(2, "puzzle id %s named %s deleted from system!" % (puzzid, puzzlename))
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

def get_puzzle_id_by_name(name):
    debug_log(4, "start, called with (name): %s" % name)

    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM puzzle WHERE name = %s LIMIT 1", (name,))
        rv = cursor.fetchone()['id']
        debug_log(4, "rv = %s" % rv)
    except:
        debug_log(2, "Puzzle name %s not found in database." % name)
        return 0
    return rv


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
    conn = mysql.connection
    cursor = conn.cursor()
    
    if part == 'solvers':
        # Handle solver assignments
        if value:  # Assign solver
            assign_solver_to_puzzle(id, value)
        else:  # Clear all solvers
            clear_puzzle_solvers(id)
    else:
        # Handle other puzzle updates
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

def check_round_completion(round_id):
    """Check if all meta puzzles in a round are solved"""
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) as total, SUM(CASE WHEN status = 'Solved' THEN 1 ELSE 0 END) as solved 
            FROM puzzle 
            WHERE round_id = %s AND ismeta = 1
            """,
            (round_id,)
        )
        result = cursor.fetchone()
        if result["total"] > 0 and result["total"] == result["solved"]:
            # All meta puzzles are solved, mark the round as solved
            cursor.execute(
                "UPDATE round SET status = 'Solved' WHERE id = %s",
                (round_id,)
            )
            conn.commit()
            debug_log(3, "Round %s marked as solved - all meta puzzles completed" % round_id)
    except:
        debug_log(1, "Error checking round completion status for round %s" % round_id)

def assign_solver_to_puzzle(puzzle_id, solver_id):
    debug_log(4, "Started with puzzle id %s" % puzzle_id) 
    conn = mysql.connection
    cursor = conn.cursor()
    
    # First, find and unassign from any other puzzle the solver is currently working on
    cursor.execute("""
        SELECT id FROM puzzle 
        WHERE JSON_CONTAINS(current_solvers, 
            JSON_OBJECT('solver_id', %s), 
            '$.solvers'
        )
    """, (solver_id,))
    current_puzzle = cursor.fetchone()
    if current_puzzle and current_puzzle['id'] != puzzle_id:
        # Unassign from current puzzle if it's different from the new one
        unassign_solver_from_puzzle(current_puzzle['id'], solver_id)
    
    # Update current solvers for the new puzzle
    cursor.execute("""
        SELECT current_solvers FROM puzzle WHERE id = %s
    """, (puzzle_id,))
    current_solvers_str = cursor.fetchone()['current_solvers'] or json.dumps({'solvers': []})
    current_solvers = json.loads(current_solvers_str)
        
    # Add new solver if not already present
    if not any(s['solver_id'] == solver_id for s in current_solvers['solvers']):
        current_solvers['solvers'].append({'solver_id': solver_id})
        cursor.execute("""
            UPDATE puzzle 
            SET current_solvers = %s 
            WHERE id = %s
        """, (json.dumps(current_solvers), puzzle_id))
    
    # Update history
    cursor.execute("""
        SELECT solver_history FROM puzzle WHERE id = %s
    """, (puzzle_id,))
    history_str = cursor.fetchone()['solver_history'] or json.dumps({'solvers': []})
    history = json.loads(history_str)
        
    # Add to history if not already present
    if not any(s['solver_id'] == solver_id for s in history['solvers']):
        history['solvers'].append({'solver_id': solver_id})
        cursor.execute("""
            UPDATE puzzle 
            SET solver_history = %s 
            WHERE id = %s
        """, (json.dumps(history), puzzle_id))
    
    conn.commit()

def unassign_solver_from_puzzle(puzzle_id, solver_id):
    conn = mysql.connection
    cursor = conn.cursor()
    
    # Update current solvers
    cursor.execute("""
        SELECT current_solvers FROM puzzle WHERE id = %s
    """, (puzzle_id,))
    current_solvers_str = cursor.fetchone()['current_solvers'] or json.dumps({'solvers': []})
    current_solvers = json.loads(current_solvers_str)
    
    current_solvers['solvers'] = [
        s for s in current_solvers['solvers'] 
        if s['solver_id'] != solver_id
    ]
    
    cursor.execute("""
        UPDATE puzzle 
        SET current_solvers = %s 
        WHERE id = %s
    """, (json.dumps(current_solvers), puzzle_id))
    
    conn.commit()

def clear_puzzle_solvers(puzzle_id):
    conn = mysql.connection
    cursor = conn.cursor()
    
    # Clear current solvers
    cursor.execute("""
        UPDATE puzzle 
        SET current_solvers = '{"solvers": []}' 
        WHERE id = %s
    """, (puzzle_id,))
    
    conn.commit()

@app.route("/puzzles/<id>/history/add", endpoint="add_solver_to_history", methods=["POST"])
@swag_from("swag/addsolvertohistory.yaml", endpoint="add_solver_to_history", methods=["POST"])
def add_solver_to_history(id):
    debug_log(4, "start. id: %s" % id)
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
        solver_id = data["solver_id"]
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception("Expected field (solver_id) missing.")

    # Check if this is a legit puzzle
    mypuzzle = get_one_puzzle(id)
    if "status" not in mypuzzle or mypuzzle["status"] != "ok":
        raise Exception("Error looking up puzzle %s" % id)

    # Check if this is a legit solver
    mysolver = get_one_solver(solver_id)
    if "status" not in mysolver or mysolver["status"] != "ok":
        raise Exception("Error looking up solver %s" % solver_id)

    conn = mysql.connection
    cursor = conn.cursor()
    
    # Get current history
    cursor.execute("""
        SELECT solver_history FROM puzzle WHERE id = %s
    """, (id,))
    history_str = cursor.fetchone()['solver_history'] or json.dumps({'solvers': []})
    history = json.loads(history_str)
    
    # Add solver to history if not already present
    if not any(s['solver_id'] == solver_id for s in history['solvers']):
        history['solvers'].append({'solver_id': solver_id})
        cursor.execute("""
            UPDATE puzzle 
            SET solver_history = %s 
            WHERE id = %s
        """, (json.dumps(history), id))
        conn.commit()
        debug_log(3, "Added solver %s to history for puzzle %s" % (solver_id, id))
    else:
        debug_log(3, "Solver %s already in history for puzzle %s" % (solver_id, id))

    return {"status": "ok"}

@app.route("/puzzles/<id>/history/remove", endpoint="remove_solver_from_history", methods=["POST"])
@swag_from("swag/removesolverfromhistory.yaml", endpoint="remove_solver_from_history", methods=["POST"])
def remove_solver_from_history(id):
    debug_log(4, "start. id: %s" % id)
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
        solver_id = data["solver_id"]
    except TypeError:
        raise Exception("failed due to invalid JSON POST structure or empty POST")
    except KeyError:
        raise Exception("Expected field (solver_id) missing.")

    # Check if this is a legit puzzle
    mypuzzle = get_one_puzzle(id)
    if "status" not in mypuzzle or mypuzzle["status"] != "ok":
        raise Exception("Error looking up puzzle %s" % id)

    # Check if this is a legit solver
    mysolver = get_one_solver(solver_id)
    if "status" not in mysolver or mysolver["status"] != "ok":
        raise Exception("Error looking up solver %s" % solver_id)

    conn = mysql.connection
    cursor = conn.cursor()
    
    # Get current history
    cursor.execute("""
        SELECT solver_history FROM puzzle WHERE id = %s
    """, (id,))
    history_str = cursor.fetchone()['solver_history'] or json.dumps({'solvers': []})
    history = json.loads(history_str)
    
    # Remove solver from history if present
    history['solvers'] = [
        s for s in history['solvers'] 
        if s['solver_id'] != solver_id
    ]
    
    cursor.execute("""
        UPDATE puzzle 
        SET solver_history = %s 
        WHERE id = %s
    """, (json.dumps(history), id))
    conn.commit()
    debug_log(3, "Removed solver %s from history for puzzle %s" % (solver_id, id))

    return {"status": "ok"}

@app.route("/config/refresh", endpoint="refresh_config", methods=["POST"])
@swag_from("swag/refreshconfig.yaml", endpoint="refresh_config", methods=["POST"])
def refresh_config():
    """Reload configuration from both YAML file and database"""
    debug_log(4, "Configuration refresh requested")
    try:
        from pblib import refresh_config
        refresh_config()
        return {"status": "ok", "message": "Configuration refreshed successfully"}
    except Exception as e:
        debug_log(1, f"Error refreshing configuration: {str(e)}")
        return {"status": "error", "message": str(e)}, 500

@app.route("/activity", methods=["GET"])
@swag_from("swag/getactivity.yaml", endpoint="activity", methods=["GET"])
def get_all_activities():
    """Get activity counts by type and puzzle timing information."""
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        
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
        activity_counts = {row['type']: row['count'] for row in activities}
        
        return jsonify({
            "status": "ok", 
            "activity": activity_counts,
            "puzzle_solves_timer": {
                "total_solves": solve_timing['total_solves'] or 0,
                "total_solve_time_seconds": solve_timing['total_solve_time'] or 0
            },
            "open_puzzles_timer": {
                "total_open": open_timing['total_open'] or 0,
                "total_open_time_seconds": open_timing['total_open_time'] or 0
            },
            "seconds_since_last_solve": last_solve['seconds_since_last_solve'] if last_solve else None
        })
    except Exception as e:
        debug_log(1, "Exception in getting activity counts: %s" % e)
        return jsonify({"status": "error", "error": str(e)}), 500

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
