import MySQLdb
import sys
import traceback
from flask import Flask, request
from flask_restful import Api, Resource
from flask_mysqldb import MySQL
from flask_restx import Api as RestXApi
from pblib import *
from pbgooglelib import *
from pbdiscordlib import *
from pandas.core.dtypes.generic import ABCIntervalIndex
from secrets import token_hex
from pbldaplib import *
from werkzeug.exceptions import HTTPException
import json
from api_models import *

app = Flask(__name__)
app.config["MYSQL_HOST"] = config["MYSQL"]["HOST"]
app.config["MYSQL_USER"] = config["MYSQL"]["USERNAME"]
app.config["MYSQL_PASSWORD"] = config["MYSQL"]["PASSWORD"]
app.config["MYSQL_DB"] = config["MYSQL"]["DATABASE"]
app.config["MYSQL_CURSORCLASS"] = "DictCursor"
mysql = MySQL(app)
api = RestXApi(app, version='1.0', title='PuzzleBoss API',
          description='API for managing puzzles, rounds, and solvers')

# Add namespaces to API
api.add_namespace(puzzle_ns)
api.add_namespace(round_ns)
api.add_namespace(solver_ns)
api.add_namespace(rbac_ns)
api.add_namespace(account_ns)
api.add_namespace(config_ns)

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


@puzzle_ns.route('/')
class PuzzleList(Resource):
    @puzzle_ns.doc('list_puzzles')
    @puzzle_ns.marshal_with(puzzle_list_model)
    def get(self):
        """List all puzzles"""
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

    @puzzle_ns.doc('create_puzzle')
    @puzzle_ns.expect(puzzle_model)
    @puzzle_ns.marshal_with(puzzle_model)
    def post(self):
        """Create a new puzzle"""
        debug_log(4, "start")
        try:
            data = puzzle_ns.payload
            puzname = sanitize_string(data["name"])
            round_id = data["round_id"]
            puzzle_uri = data["puzzle_uri"]
            debug_log(5, "request data is - %s" % str(data))
        except TypeError:
            raise Exception("failed due to invalid JSON POST structure or empty POST")
        except KeyError:
            raise Exception("One or more expected fields (name, round_id, puzzle_uri) missing.")

        if not puzname or puzname == "":
            raise Exception("Puzzle with empty name disallowed")

        # Check for duplicate
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM puzzle WHERE name = %s LIMIT 1", (puzname,))
            existing_puzzle = cursor.fetchone()
        except:
            raise Exception("Exception checking database for duplicate puzzle before insert")

        if existing_puzzle:
            raise Exception("Duplicate puzzle name %s detected" % puzname)

        chat_status = chat_announce_puzzle(puzname)
        debug_log(4, "return from announcing puzzle in chat is - %s" % str(chat_status))

        if chat_status == None:
            raise Exception("Error in announcing new puzzle in chat")

        debug_log(4, "Making call to create google drive sheet for puzzle")
        drive_id = create_puzzle_sheet(puzname)
        drive_uri = "https://drive.google.com/drive/u/1/folders/%s" % drive_id
        debug_log(5, "Puzzle drive URI created: %s" % drive_uri)

        # Actually insert into the database
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO puzzle (name, round_id, puzzle_uri, drive_uri) VALUES (%s, %s, %s, %s)",
                (puzname, round_id, puzzle_uri, drive_uri),
            )
            conn.commit()
            myid = cursor.lastrowid
        except:
            raise Exception("Exception in insertion of puzzle %s into database" % puzname)

        debug_log(
            3, "puzzle %s added to database! drive_uri: %s" % (puzname, drive_uri)
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

@puzzle_ns.route('/<int:id>')
@puzzle_ns.param('id', 'The puzzle identifier')
class Puzzle(Resource):
    @puzzle_ns.doc('get_puzzle')
    @puzzle_ns.marshal_with(puzzle_model)
    def get(self, id):
        """Fetch a puzzle given its identifier"""
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

        debug_log(4, "fetched puzzle %s" % id)
        return {
            "status": "ok",
            "puzzle": puzzle,
        }

@puzzle_ns.route('/<int:id>/<string:part>')
@puzzle_ns.param('id', 'The puzzle identifier')
@puzzle_ns.param('part', 'The part to update')
class PuzzlePart(Resource):
    @puzzle_ns.doc('get_puzzle_part')
    def get(self, id, part):
        """Get a specific part of a puzzle"""
        debug_log(4, "start. id: %s, part: %s" % (id, part))
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute(f"SELECT {part} from puzzle_view where id = %s", (id,))
            answer = cursor.fetchone()[part]
        except TypeError:
            raise Exception("Puzzle %s not found in database" % id)
        except:
            raise Exception(
                "Exception in fetching %s part for puzzle %s from database" % (part, id)
            )

        if part == "puzzles":
            answer = get_puzzles_from_list(answer)

        debug_log(4, "fetched puzzle part %s for %s" % (part, id))
        return {"status": "ok", "puzzle": {"id": id, part: answer}}

    @puzzle_ns.doc('update_puzzle_part')
    @puzzle_ns.expect(puzzle_model)
    def post(self, id, part):
        """Update a specific part of a puzzle"""
        debug_log(4, "start. id: %s, part: %s" % (id, part))
        try:
            data = puzzle_ns.payload
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

        # Actually insert into the database
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute(f"UPDATE puzzle SET {part} = %s WHERE id = %s", (value, id))
            conn.commit()
        except KeyError:
            raise Exception(
                "Exception in modifying %s of puzzle %s into database" % (part, id)
            )

        debug_log(3, "puzzle %s %s updated to %s" % (id, part, value))

        return {"status": "ok", "puzzle": {"id": id, part: value}}


@round_ns.route('/')
class RoundList(Resource):
    @round_ns.doc('list_rounds')
    @round_ns.marshal_with(round_list_model)
    def get(self):
        """List all rounds"""
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

    @round_ns.doc('create_round')
    @round_ns.expect(round_model)
    @round_ns.marshal_with(round_model)
    def post(self):
        """Create a new round"""
        debug_log(4, "start")
        try:
            data = round_ns.payload
            roundname = sanitize_string(data["name"])
            round_uri = data["round_uri"]
            debug_log(5, "request data is - %s" % str(data))
        except TypeError:
            raise Exception("failed due to invalid JSON POST structure or empty POST")
        except KeyError:
            raise Exception("Expected field (name, round_uri) missing.")

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
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO round (name, drive_uri, round_uri) VALUES (%s, %s, %s)",
                (roundname, round_drive_uri, round_uri),
            )
            conn.commit()
        except:
            raise Exception("Exception in insertion of round %s into database" % roundname)

        debug_log(
            3, "round %s added to database! drive_uri: %s" % (roundname, round_drive_uri)
        )

        return {"status": "ok", "round": {"name": roundname}}

@round_ns.route('/<int:id>')
@round_ns.param('id', 'The round identifier')
class Round(Resource):
    @round_ns.doc('get_round')
    @round_ns.marshal_with(round_model)
    def get(self, id):
        """Fetch a round given its identifier"""
        debug_log(4, "start. id: %s" % id)
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
            cursor.execute("SELECT * from round_view where id = %s", (id,))
            round = cursor.fetchone()
        except TypeError:
            raise Exception("Round %s not found in database" % id)
        except:
            raise Exception("Exception in fetching round %s from database" % id)

        debug_log(4, "fetched round %s" % id)
        return {
            "status": "ok",
            "round": round,
        }

@round_ns.route('/<int:id>/<string:part>')
@round_ns.param('id', 'The round identifier')
@round_ns.param('part', 'The part to update')
class RoundPart(Resource):
    @round_ns.doc('get_round_part')
    def get(self, id, part):
        """Get a specific part of a round"""
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

    @round_ns.doc('update_round_part')
    @round_ns.expect(round_model)
    def post(self, id, part):
        """Update a specific part of a round"""
        debug_log(4, "start. id: %s, part: %s" % (id, part))
        try:
            data = round_ns.payload
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


@solver_ns.route('/')
class SolverList(Resource):
    @solver_ns.doc('list_solvers')
    @solver_ns.marshal_with(solver_list_model)
    def get(self):
        """List all solvers"""
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

    @solver_ns.doc('create_solver')
    @solver_ns.expect(solver_model)
    @solver_ns.marshal_with(solver_model)
    def post(self):
        """Create a new solver"""
        debug_log(4, "start")
        try:
            data = solver_ns.payload
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

@solver_ns.route('/<int:id>')
@solver_ns.param('id', 'The solver identifier')
class Solver(Resource):
    @solver_ns.doc('get_solver')
    @solver_ns.marshal_with(solver_model)
    def get(self, id):
        """Fetch a solver given its identifier"""
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

@solver_ns.route('/<int:id>/<string:part>')
@solver_ns.param('id', 'The solver identifier')
@solver_ns.param('part', 'The part to update')
class SolverPart(Resource):
    @solver_ns.doc('get_solver_part')
    def get(self, id, part):
        """Get a specific part of a solver"""
        debug_log(4, "start. id: %s, part: %s" % (id, part))
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute(f"SELECT {part} from solver_view where id = %s", (id,))
            answer = cursor.fetchone()[part]
        except TypeError:
            raise Exception("Solver %s not found in database" % id)
        except:
            raise Exception(
                "Exception in fetching %s part for solver %s from database" % (part, id)
            )

        debug_log(4, "fetched solver part %s for %s" % (part, id))
        return {"status": "ok", "solver": {"id": id, part: answer}}

    @solver_ns.doc('update_solver_part')
    @solver_ns.expect(solver_model)
    def post(self, id, part):
        """Update a specific part of a solver"""
        debug_log(4, "start. id: %s, part: %s" % (id, part))
        try:
            data = solver_ns.payload
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

        # Actually insert into the database
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute(f"UPDATE solver SET {part} = %s WHERE id = %s", (value, id))
            conn.commit()
        except KeyError:
            raise Exception(
                "Exception in modifying %s of solver %s into database" % (part, id)
            )

        debug_log(3, "solver %s %s updated to %s" % (id, part, value))

        return {"status": "ok", "solver": {"id": id, part: value}}


@config_ns.route('/')
class Config(Resource):
    @config_ns.doc('get_config')
    def get(self):
        """Get all configuration values"""
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

    @config_ns.doc('update_config')
    @config_ns.expect(config_model)
    def post(self):
        """Update a configuration value"""
        debug_log(4, "start")
        try:
            data = config_ns.payload
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

@config_ns.route('/refresh')
class RefreshConfig(Resource):
    @config_ns.doc('refresh_config')
    def post(self):
        """Reload configuration from both YAML file and database"""
        debug_log(4, "Configuration refresh requested")
        try:
            from pblib import refresh_config
            refresh_config()
            return {"status": "ok", "message": "Configuration refreshed successfully"}
        except Exception as e:
            debug_log(0, f"Error refreshing configuration: {str(e)}")
            return {"status": "error", "message": str(e)}, 500

# POST/WRITE Operations

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

@rbac_ns.route('/<string:priv>/<int:uid>')
@rbac_ns.param('priv', 'The privilege category')
@rbac_ns.param('uid', 'The user ID')
class RBAC(Resource):
    @rbac_ns.doc('check_priv')
    def get(self, priv, uid):
        """Check if a user has a specific privilege"""
        debug_log(4, "start. priv: %s, uid: %s" % (priv, uid))
        try:
            conn = mysql.connection
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM privs WHERE uid = %s", (uid,))
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
                % (priv, uid)
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

    @rbac_ns.doc('set_priv')
    @rbac_ns.expect(rbac_model)
    def post(self, priv, uid):
        """Set a privilege for a user"""
        debug_log(4, "start. priv: %s, uid %s" % (priv, uid))
        try:
            data = rbac_ns.payload
            debug_log(4, "post data: %s" % (data))
            value = data["allowed"]
            if (value != "YES" and value != "NO"):
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

@account_ns.route('/')
class Account(Resource):
    @account_ns.doc('create_account')
    @account_ns.expect(new_account_model)
    def post(self):
        """Create a new account"""
        debug_log(4, "start.")
        try:
            data = account_ns.payload
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
                    % (username, email)
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

@account_ns.route('/finish/<string:code>')
@account_ns.param('code', 'The verification code')
class FinishAccount(Resource):
    @account_ns.doc('finish_account')
    def get(self, code):
        """Finish account registration with verification code"""
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

@account_ns.route('/delete/<string:username>')
@account_ns.param('username', 'The username to delete')
class DeleteAccount(Resource):
    @account_ns.doc('delete_account')
    def get(self, username):
        """Delete an account"""
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
        debug_log(0, "Error checking round completion status for round %s" % round_id)

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
