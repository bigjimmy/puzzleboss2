import MySQLdb
import sys
import flasgger
import pblib
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

app = Flask(__name__)
app.config["MYSQL_HOST"] = config["MYSQL"]["HOST"]
app.config["MYSQL_USER"] = config["MYSQL"]["USERNAME"]
app.config["MYSQL_PASSWORD"] = config["MYSQL"]["PASSWORD"]
app.config["MYSQL_DB"] = config["MYSQL"]["DATABASE"]
mysql = MySQL(app)
api = Api(app)
swagger = flasgger.Swagger(app)

# GET/READ Operations

@app.route("/puzzles", endpoint="puzzles", methods=["GET"])
@swag_from("swag/getpuzzles.yaml", endpoint="puzzles", methods=["GET"])
def get_all_puzzles():
    debug_log(4, "start")
    result = {}
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("""SELECT id,name from puzzle""")
        rv = cursor.fetchall()
    except IndexError:
        errmsg = "Exception in fetching all puzzles from database"
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    result["status"] = "ok"

    puzzlist = []
    for puzz in rv:
        puzzlist.append({"id": puzz[0], "name": puzz[1]})
    result["puzzles"] = puzzlist

    debug_log(4, "listed all puzzles")
    return result, 200


@app.route("/puzzles/<id>", endpoint="puzzle_id", methods=["GET"])
@swag_from("swag/getpuzzleid.yaml", endpoint="puzzle_id", methods=["GET"])
def get_one_puzzle(id):
    debug_log(4, "start. id: %s" % id)
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("""SELECT * from puzzle_view where id = %s""", [id])
        rv = cursor.fetchall()[0]
    except IndexError:
        errmsg = "Puzzle %s not found in database" % id
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except:
        errmsg = "Exception in fetching puzzle %s from database" % id
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    debug_log(5, "fetched puzzle %s: %s" % (id, rv))
    lastact = get_last_activity_for_puzzle(id)
    return {
        "status": "ok",
        "puzzle": {
            "id": rv[0],
            "name": rv[1],
            "drive_link": rv[2],
            "status": rv[3],
            "answer": rv[4],
            "roundname": rv[5],
            "round_id": rv[6],
            "comments": rv[7],
            "drive_uri": rv[8],
            "chat_channel_name": rv[9],
            "chat_channel_id": rv[10],
            "chat_channel_link": rv[11],
            "drive_id": rv[12],
            "puzzle_uri": rv[13],
            "solvers": rv[14],
            "cursolvers": rv[15],
            "xyzloc": rv[16],
            "lastact": lastact,
        },
    }, 200


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
            sql = "SELECT %s from puzzle_view where id = %s" % (part, id)
            cursor.execute(sql)
            rv = cursor.fetchone()[0]
        except TypeError:
            errmsg = "Puzzle %s not found in database" % id
            debug_log(1, errmsg)
            return {"error": errmsg}, 500
        except:
            errmsg = "Exception in fetching %s part for puzzle %s from database" % (
                part,
                id,
            )
            debug_log(0, errmsg)
            return {"error": errmsg}, 500

    debug_log(4, "fetched puzzle part %s for %s" % (part, id))
    return {"status": "ok", "puzzle": {"id": id, part: rv}}, 200


@app.route("/rounds", endpoint="rounds", methods=["GET"])
@swag_from("swag/getrounds.yaml", endpoint="rounds", methods=["GET"])
def get_all_rounds():
    result = {}
    debug_log(4, "start")
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("""SELECT id,name from round""")
        rv = cursor.fetchall()
    except:
        errmsg = "Exception in fetching all rounds from database"
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

        result["status"] = "ok"

    roundlist = []
    for round in rv:
        roundlist.append({"id": round[0], "name": round[1]})
    result["rounds"] = roundlist

    debug_log(4, "listed all rounds")
    return result, 200


@app.route("/rounds/<id>", endpoint="round_id", methods=["GET"])
@swag_from("swag/getroundid.yaml", endpoint="round_id", methods=["GET"])
def get_one_round(id):
    debug_log(4, "start. id: %s" % id)
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("""SELECT * from round_view where id = %s""", [id])
        rv = cursor.fetchall()[0]
    except IndexError:
        errmsg = "Round %s not found in database" % id
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except:
        errmsg = "Exception in fetching round %s from database" % id
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    puzzlesstruct = get_puzzles_from_list(rv[6])

    debug_log(4, "fetched round %s" % id)
    return {
        "status": "ok",
        "round": {
            "id": rv[0],
            "name": rv[1],
            "round_uri": rv[2],
            "drive_uri": rv[3],
            "drive_id": rv[4],
            "meta_id": rv[5],
            "puzzles": puzzlesstruct,
        },
    }, 200


@app.route("/rounds/<id>/<part>", endpoint="round_part", methods=["GET"])
@swag_from("swag/getroundpart.yaml", endpoint="round_part", methods=["GET"])
def get_round_part(id, part):
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        sql = "SELECT %s from round_view where id = %s" % (part, id)
        cursor.execute(sql)
        rv = cursor.fetchone()[0]
    except TypeError:
        errmsg = "Round %s not found in database" % id
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except:
        errmsg = "Exception in fetching %s part for round %s from database" % (part, id)
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    answer = rv

    if part == "puzzles":
        puzlist = get_puzzles_from_list(rv)
        answer = puzlist

    debug_log(4, "fetched round part %s for %s" % (part, id))
    return {"status": "ok", "round": {"id": id, part: answer}}, 200


@app.route("/solvers", endpoint="solvers", methods=["GET"])
@swag_from("swag/getsolvers.yaml", endpoint="solvers", methods=["GET"])
def get_all_solvers():
    result = {}
    debug_log(4, "start")
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("""SELECT id,name from solver_view""")
        rv = cursor.fetchall()
    except:
        errmsg = "Exception in fetching all solvers from database"
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

        result["status"] = "ok"

    solverlist = []
    for solver in rv:
        solverlist.append({"id": solver[0], "name": solver[1]})
    result["solvers"] = solverlist

    debug_log(4, "listed all solvers")
    return result, 200


@app.route("/solvers/<id>", endpoint="solver_id", methods=["GET"])
@swag_from("swag/getsolverid.yaml", endpoint="solver_id", methods=["GET"])
def get_one_solver(id):
    debug_log(4, "start. id: %s" % id)
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("""SELECT * from solver_view where id = %s""", [id])
        rv = cursor.fetchall()[0]
    except IndexError:
        errmsg = "Solver %s not found in database" % id
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except:
        errmsg = "Exception in fetching solver %s from database" % id
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    lastact = get_last_activity_for_solver(id)
    debug_log(4, "fetched solver %s" % id)
    return {
        "status": "ok",
        "solver": {
            "id": rv[0],
            "name": rv[1],
            "puzzles": rv[2],
            "puzz": rv[3],
            "fullname": rv[4],
            "chat_uid": rv[5],
            "chat_name": rv[6],
            "lastact" : lastact
        },
    }, 200

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
            sql = "SELECT %s from solver_view where id = %s" % (part, id)
            cursor.execute(sql)
            rv = cursor.fetchone()[0]
        except TypeError:
            errmsg = "Solver %s not found in database" % id
            debug_log(1, errmsg)
            return {"error" : errmsg }, 500
        except:
            errmsg = "Exception in fetching %s part for solver %s from database" % (part, id)
            debug_log(0, errmsg)
            return {"error" : errmsg }, 500
        
    debug_log(4, "fetched round part %s for %s" % (part, id))
    return {
            "status" : "ok",
            "solver" : {
                        "id" : id,
                        part : rv}
            }, 200

@app.route("/version", endpoint="version", methods=["GET"])
@swag_from("swag/getversion.yaml", endpoint="version", methods=["GET"])
def get_current_version():
    debug_log(4, "start")
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(version) from log")
        rv = cursor.fetchone()[0]
    except:
        errmsg = "Exception in fetching latest version from database"
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    debug_log(5, "fetched latest version number: %s from database" % str(rv))
    return {"status": "ok", "version": rv}, 200


@app.route("/version/<fromver>/<tover>", endpoint="version_diff", methods=["GET"])
@swag_from("swag/getversiondiff.yaml", endpoint="version_diff", methods=["GET"])
def get_diff(fromver, tover):
    debug_log(4, "start. fromver: %s, tover: %s" % (fromver, tover))

    if fromver > tover:
        errmsg = "Version numbers being compared must be in order."
        debug_log(1, errmsg)
        return {"error": errmsg}

    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(
            """ SELECT DISTINCT * FROM log WHERE log.version >= %s AND log.version <= %s """,
            (fromver, tover),
        )
        rv = cursor.fetchall()
    except TypeError:
        errmsg = "Exception fetching version diff from %s to %s from database" % (
            fromver,
            tover,
        )
        debug_log(0, errmsg)
        return {"error": errmsg}

    versionlist = []
    for version in rv:
        versionlist.append(
            {
                "version": version[0],
                "module": version[3],
                "name": version[4],
                "id": version[5],
                "part": version[6],
            }
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
        cursor.execute(""" SELECT DISTINCT * FROM log """)
        rv = cursor.fetchall()
    except TypeError:
        errmsg = "Exception fetching all-time version diff from database"
        debug_log(0, errmsg)
        return {"error": errmsg}

    versionlist = []
    for version in rv:
        versionlist.append(
            {
                "version": version[0],
                "module": version[3],
                "name": version[4],
                "id": version[5],
                "part": version[6],
            }
        )

    debug_log(5, "fetched all-time version diff")
    return {"status": "ok", "versions": versionlist}


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
        errmsg = "failed due to invalid JSON POST structure or empty POST"
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except KeyError:
        errmsg = "One or more expected fields (name, puzzle_uri, round_id) missing."
        debug_log(1, errmsg)
        return {"error": errmsg}, 500

    # Check for duplicate
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("""SELECT id FROM puzzle WHERE name=%s""", [puzname])
        rv = cursor.fetchall()
    except:
        errmsg = "Exception checking database for duplicate puzzle before insert"
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    if rv != ():
        errmsg = "Duplicate puzzle name %s detected" % puzname
        debug_log(2, errmsg)
        return {"error": errmsg}, 500

    # Get round drive link and name
    round_drive_uri = get_round_part(roundid, "drive_uri")[0]["round"]["drive_uri"]
    round_name = get_round_part(roundid, "name")[0]["round"]["name"]
    round_drive_id = round_drive_uri.split("/")[-1]

    # Make new channel so we can get channel id and link (use doc redirect hack since no doc yet)
    drive_uri = "%s/doc.php?pname=%s" % (config["APP"]["BIN_URI"], puzname)
    chat_channel = chat_create_channel_for_puzzle(
        puzname, round_name, puzuri, drive_uri
    )
    debug_log(4, "return from creating chat channel is - %s" % str(chat_channel))
    try:
        chat_id = chat_channel[0]
        chat_link = chat_channel[1]
    except:
        errmsg = "Error in creating chat channel for puzzle"
        debug_log(0, errmsg)
        return {"error": errmsg}, 500
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
            """INSERT INTO puzzle
                       (name, puzzle_uri, round_id, chat_channel_id, chat_channel_link, chat_channel_name, drive_id, drive_uri, drive_link)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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
        errmsg = (
            "MySQL integrity failure. Does another puzzle with the same name %s exist?"
            % puzname
        )
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except:
        errmsg = "Exception in insertion of puzzle %s into database" % puzname
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    # We need to figure out what the ID is that the puzzle got assigned
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("""SELECT id FROM puzzle WHERE name=%s""", [puzname])
        rv = cursor.fetchall()
        myid = str(rv[0][0])
    except:
        errmsg = "Exception checking database for puzzle after insert"
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

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
    }, 200


@app.route("/rounds", endpoint="post_rounds", methods=["POST"])
@swag_from("swag/putround.yaml", endpoint="post_rounds", methods=["POST"])
def create_round():
    debug_log(4, "start")
    try:
        data = request.get_json()
        roundname = sanitize_string(data["name"])
        debug_log(5, "request data is - %s" % str(data))
    except TypeError:
        errmsg = "failed due to invalid JSON POST structure or empty POST"
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except KeyError:
        errmsg = "Expected field (name) missing."
        debug_log(1, errmsg)
        return {"error": errmsg}, 500

    if not roundname or roundname == "":
        errmsg = "Round with empty name disallowed"
        debug_log(2, errmsg)
        return {"error": errmsg}, 500

    # Check for duplicate
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute("""SELECT id FROM round WHERE name=%s""", [roundname])
        rv = cursor.fetchall()
    except:
        errmsg = "Exception checking database for duplicate round before insert"
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    if rv != ():
        errmsg = "Duplicate round name %s detected" % roundname
        debug_log(2, errmsg)
        return {"error": errmsg}, 500

    chat_status = chat_announce_round(roundname)
    debug_log(4, "return from announcing round in chat is - %s" % str(chat_status))

    if chat_status == None:
        errmsg = "Error in announcing new round in chat"
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    debug_log(4, "Making call to create google drive folder for round")
    round_drive_id = create_round_folder(roundname)
    round_drive_uri = "https://drive.google.com/drive/u/1/folders/%s" % round_drive_id
    debug_log(5, "Round drive URI created: %s" % round_drive_uri)
    # Actually insert into the database
    # try:
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO round (name, drive_uri) VALUES (%s, %s)""",
        (roundname, round_drive_uri),
    )
    conn.commit()
    # except:
    #     errmsg = "Exception in insertion of round %s into database" % roundname
    #     debug_log(0, errmsg)
    #     return {"error" : errmsg }, 500

    debug_log(
        3, "round %s added to database! drive_uri: %s" % (roundname, round_drive_uri)
    )

    return {"status": "ok", "round": {"name": roundname}}, 200


@app.route("/rounds/<id>/<part>", endpoint="post_round_part", methods=["POST"])
@swag_from("swag/putroundpart.yaml", endpoint="post_round_part", methods=["POST"])
def update_round_part(id, part):
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    try:
        data = request.get_json()
        value = data[part]
        debug_log(5, "request data is - %s" % str(data))
    except TypeError:
        errmsg = "failed due to invalid JSON POST structure or empty POST"
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except KeyError:
        errmsg = "Expected field (%s) missing." % part
        debug_log(1, errmsg)
        return {"error": errmsg}, 500

    # Actually insert into the database
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        sql = "UPDATE round SET %s = %s WHERE id = %s" % (part, value, id)
        cursor.execute(sql)
        conn.commit()
    except KeyError:
        errmsg = "Exception in modifying %s of round %s into database" % (part, id)
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    debug_log(3, "round %s %s updatedL %s" % (id, part, sql))

    return {"status": "ok", "round": {"id": id, part: value}}, 200


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
        errmsg = "failed due to invalid JSON POST structure or empty POST"
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except KeyError:
        errmsg = "One or more expected fields (name, fullname) missing."
        debug_log(1, errmsg)
        return {"error": errmsg}, 500

    # Actually insert into the database
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO solver (name, fullname) VALUES (%s, %s)""", (name, fullname)
        )
        conn.commit()
    except MySQLdb._exceptions.IntegrityError:
        errmsg = (
            "MySQL integrity failure. Does another solver with the same name %s exist?"
            % name
        )
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except:
        errmsg = "Exception in insertion of solver %s into database" % name
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    debug_log(3, "solver %s added to database!" % name)

    return {"status": "ok", "solver": {"name": name, "fullname": fullname}}, 200


@app.route("/solvers/<id>/<part>", endpoint="post_solver_part", methods=["POST"])
@swag_from("swag/putsolverpart.yaml", endpoint="post_solver_part", methods=["POST"])
def update_solver_part(id, part):
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
        value = data[part]
    except TypeError:
        errmsg = "failed due to invalid JSON POST structure or empty POST"
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except KeyError:
        errmsg = "Expected %s field missing" % part
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    # Check if this is a legit solver
    mysolver = get_one_solver(id)[0]
    debug_log(5, "return value from get_one_solver %s is %s" % (id, mysolver))
    if "status" not in mysolver or mysolver["status"] != "ok":
        errmsg = "Error looking up solver %s" % id
        debug_log(1, errmsg)
        return {"error": errmsg}, 500

    # This is a change to the solver's claimed puzzle
    if part == "puzz":
        if value:
            # Assigning puzzle, so check if puzzle is real
            debug_log(4, "trying to assign solver %s to puzzle %s" % (id, value))
            mypuzz = get_one_puzzle(value)[0]
            debug_log(5, "return value from get_one_puzzle %s is %s" % (value, mypuzz))
            if mypuzz["status"] != "ok":
                errmsg = (
                    "Error retrieving info on puzzle %s, which user %s is attempting to claim"
                    % (value, id)
                )
                debug_log(1, errmsg)
                return {"error": errmsg}, 500
            # Since we're assigning, the puzzle should automatically transit out of "NEW" state if it's there
            if mypuzz["puzzle"]["status"] == "New":
                debug_log(
                    3,
                    "Automatically marking puzzle id %s, name %s as being worked on."
                    % (mypuzz["puzzle"]["id"], mypuzz["puzzle"]["name"]),
                )
                update_puzzle_part_in_db(value, "status", "Being worked")

            # Reject attempt to assign to a solved puzzle
            if mypuzz["puzzle"]["status"] == "Solved":
                errmsg = "Can't assign to a solved puzzle!"
                debug_log(2, errmsg)
                return {"error": errmsg}, 500

        else:
            # Puzz is empty, so this is a de-assignment. Populate the db with empty string for it.
            value = "NULL"

        # Now log it in the activity table
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            sql = (
                "INSERT INTO activity (puzzle_id, solver_id, source, type) VALUES (%s, %s, '%s', '%s')"
                % (value, id, "apache", "interact")
            )
            cursor.execute(sql)
            conn.commit()
        except TypeError:
            errmsg = (
                "Exception in logging change to puzzle %s in activity table for solver %s in database"
                % (value, id)
            )
            debug_log(0, errmsg)
            return {"error": errmsg}, 500

        debug_log(4, "Activity table updated: solver %s taking puzzle %s" % (id, value))

        # Now actually assign puzzle to solver
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            sql = "INSERT INTO puzzle_solver (puzzle_id, solver_id) VALUES (%s, %s)" % (
                value,
                id,
            )
            cursor.execute(sql)
            conn.commit()
        except:
            errmsg = "Exception in setting solver to %s for puzzle %s" % (id, value)
            debug_log(0, errmsg)
            return {"error": errmsg}, 500

        debug_log(3, "Solver %s claims to be working on %s" % (id, value))

        return {"status": "ok", "solver": {"id": id, part: value}}, 200

    # This is actually a change to the solver's info
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        sql = "UPDATE solver SET %s = '%s' WHERE id = %s" % (part, value, id)
        cursor.execute(sql)
        conn.commit()
    except:
        errmsg = "Exception in modifying %s of solver %s in database" % (part, id)
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    debug_log(3, "solver %s %s updated in database" % (id, part))

    return {"status": "ok", "solver": {"id": id, part: value}}, 200


@app.route("/puzzles/<id>/<part>", endpoint="post_puzzle_part", methods=["POST"])
@swag_from("swag/putpuzzlepart.yaml", endpoint="post_puzzle_part", methods=["POST"])
def update_puzzle_part(id, part):
    debug_log(4, "start. id: %s, part: %s" % (id, part))
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
        value = data[part]
    except TypeError:
        errmsg = "failed due to invalid JSON POST structure or empty POST"
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except KeyError:
        errmsg = "Expected %s field missing" % part
        debug_log(1, errmsg)
        return {"error": errmsg}, 500

    # Check if this is a legit puzzle
    mypuzzle = get_one_puzzle(id)[0]
    debug_log(5, "return value from get_one_puzzle %s is %s" % (id, mypuzzle))
    if "status" not in mypuzzle or mypuzzle["status"] != "ok":
        errmsg = "Error looking up puzzle %s" % id
        debug_log(1, errmsg)
        return {"error": errmsg}, 500

    if part == "lastact":
        set_new_activity_for_puzzle(id, value)

    elif part == "status":
        debug_log(4, "part to update is status")
        if value == "Solved":
            if mypuzzle["puzzle"]["status"] == "Solved":
                errmsg = "Puzzle %s is already solved! Refusing to re-solve." % id
                debug_log(2, errmsg)
                return {"error": errmsg}, 500
            # Don't mark puzzle as solved if there is no answer filled in
            if not mypuzzle["puzzle"]["answer"]:
                errmsg = "Puzzle %s has no answer! Refusing to mark as solved." % id
                debug_log(2, errmsg)
                return {"error": errmsg}, 500
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
        ):
            update_puzzle_part_in_db(id, part, value)
            chat_announce_attention(mypuzzle["puzzle"]["name"])

    elif part == "xyzloc":
        update_puzzle_part_in_db(id, part, value)
        chat_say_something(
            mypuzzle["puzzle"]["chat_channel_id"],
            "**ATTENTION:** %s is being worked on at %s"
            % (mypuzzle["puzzle"]["name"], value),
        )

    elif part == "answer":
        if data != "":
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
    else:
        errmsg = "Invalid part name %s" % part
        debug_log(2, errmsg)
        return {"error": errmsg}, 500

    debug_log(
        3,
        "puzzle name %s, id %s, part %s has been set to %s"
        % (mypuzzle["puzzle"]["name"], id, part, value),
    )

    return {"status": "ok", "puzzle": {"id": id, part: value}}, 200


@app.route("/account", endpoint="post_new_account", methods=["POST"])
@swag_from("swag/putnewaccount.yaml", endpoint="post_new_account", methods=["POST"])
def new_account():
    debug_log(4, "start.")
    try:
        data = request.get_json()
        debug_log(5, "request data is - %s" % str(data))
        username = data['username']
        fullname = data['fullname']
        email = data['email']
        password = data['password']
        reset = data.get('reset')
    except TypeError:
        errmsg = "failed due to invalid JSON POST structure or empty POST"
        debug_log(1, errmsg)
        return {"error": errmsg}, 500
    except KeyError:
        errmsg = "Expected field missing (username, fullname, email, or password)"
        debug_log(1, errmsg)
        return {"error": errmsg}, 500

    allusers = get_all_solvers()[0]['solvers']
    userfound = False
    for solver in allusers:
        if solver['name'] == username:
            if reset == "reset":
                userfound = True
                debug_log(3, "Password reset attempt detected for user %s" % username)
            else:
                errmsg = "Username %s already exists. Pick another, or add reset flag." % username
                debug_log(2, errmsg)
                return {"error": errmsg}, 500
    
    if reset == "reset": 
        if not userfound:
            errmsg = "Username %s not found in system to reset." % username
            debug_log(2, errmsg)
            return {"error": errmsg}, 500
        if verify_email_for_user(email, username) != 1:
            errmsg = "Username %s does not match email %s in the system." % (username, email)
            debug_log(2, errmsg)
            return {"error": errmsg}, 500

    # Generate the code
    code = token_hex(4)
    debug_log(4, "code picked: %s" % code)
    
    # Actually insert into the database
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO newuser (username, fullname, email, password, code) 
            VALUES (%s, %s, %s, %s, %s)""", (username, fullname, email, password, code)
        )
        conn.commit()
    except TypeError:
        errmsg = "Exception in insertion of unverified user request %s into database" % username
        debug_log(0, errmsg)
        return {"error": errmsg}, 500

    debug_log(3, "unverified new user %s added to database with verification code %s" % (username, code))

    return {"status": "ok", "code": code}, 200


############### END REST calls section


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
