import yaml
import inspect
import datetime
import bleach

with open("puzzleboss.yaml") as f:
    config = yaml.load(f, Loader=yaml.FullLoader)

huntfolderid = "undefined"


def debug_log(sev, message):
    # Levels:
    # 0 = emergency
    # 1 = error
    # 2 = warning
    # 3 = info
    # 4 = debug
    # 5 = trace

    if config["APP"]["LOGLEVEL"] >= sev:
        timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        print(
            "[%s] [SEV%s] %s: %s"
            % (timestamp, sev, inspect.currentframe().f_back.f_code.co_name, message),
            flush=True
        )
    return


def sanitize_string(mystring):
    outstring = "".join(e for e in mystring if e.isalnum())
    return outstring


def unassign_solver_by_name(name):
    debug_log(4, "start, called with (name): %s" % name)

    # We have to look up the solver id for the given name first.
    conn = mysql.connection
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM solver_view WHERE name = '%s'" % name)
    id = cursor.fetchall()[0][0]
    sql = "INSERT INTO puzzle_solver (puzzle_id, solver_id) VALUES (NULL, %s)" % id
    cursor = conn.cursor()
    cursor.execute(sql)
    conn.commit()

    debug_log(3, "Solver id: %s, name: %s unassigned" % (id, name))

    return 0


def clear_puzzle_solvers(id):
    debug_log(4, "start, called with (id): %s" % id)

    mypuzzle = get_one_puzzle(id)[0]
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
    sql = "UPDATE puzzle SET %s = '%s' WHERE id = %s" % (part, value, id)
    cursor.execute(sql)
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
        puzarray.append(get_one_puzzle(mypuz)[0]["puzzle"])

    debug_log(4, "puzzle list assembled is: %s" % puzarray)
    return puzarray


def get_last_activity_for_puzzle(id):
    debug_log(4, "start, called with: %s" % id)
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * from activity where puzzle_id = %s ORDER BY time DESC LIMIT 1""",
            [id],
        )
        arv = cursor.fetchall()[0]
    except IndexError:
        errmsg = "No Activity for Puzzle %s found in database yet" % id
        debug_log(4, errmsg)
        return None

    return {
            "actid" : arv[0],
            "timestamp" : arv[1],
            "solver_id" : arv[2],
            "puzzle_id" : arv[3],
            "source" : arv[4],
            "type" : arv[5]
            }
    
def get_last_activity_for_solver(id):
    debug_log(4, "start, called with: %s" % id)
    try:
        conn = mysql.connection
        cursor = conn.cursor()
        cursor.execute('''SELECT * from activity where solver_id = %s ORDER BY time DESC LIMIT 1''', [id])
        arv = cursor.fetchall()[0]
    except IndexError:
        errmsg = "No Activity for solver %s found in database yet" % id
        debug_log(4, errmsg)
        return None

    return {
            "actid" : arv[0],
            "timestamp" : arv[1],
            "solver_id" : arv[2],
            "puzzle_id" : arv[3],
            "source" : arv[4],
            "type" : arv[5]
            }
    
def set_new_activity_for_puzzle(id, actstruct):
    debug_log(4, "start, called for puzzle id %s with: %s" % (id, actstruct))

    try:
        solver_id = actstruct["solver_id"]
        puzzle_id = id
        source = actstruct["source"]
        type = actstruct["type"]
    except:
        errmsg = (
            "Failure parsing activity dict. Needs solver_id, source, type. dict passed in is: %s"
            % actstruct
        )
        return 255

    try:
        conn = mysql.connection
        cursor = conn.cursor()
        sql = (
            "INSERT INTO activity (puzzle_id, solver_id, source, type) VALUES (%s, %s, '%s', '%s')"
            % (puzzle_id, solver_id, source, type)
        )
        cursor.execute(sql)
        conn.commit()
    except TypeError:
        errmsg = (
            "Exception in logging change to puzzle %s in activity table for solver %s in database"
            % (value, id)
        )
        debug_log(0, errmsg)
        return 255

    debug_log(3, "Updated activity for puzzle id %s" % (puzzle_id))
    return 0
