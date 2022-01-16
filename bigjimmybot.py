import sys
import pblib
import pbrest
import requests
import json
import time
import datetime
import threading
import queue
from queue import *
from threading import *
from pblib import debug_log, sanitize_string, config
from pbgooglelib import *
from pbdiscordlib import *

exitFlag = 0
queueLock = threading.Lock()
workQueue = queue.Queue(300)
threadID = 1
threads = []


class puzzThread(threading.Thread):
    def __init__(self, threadID, name, q, fromtime=datetime.datetime.fromordinal(1)):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.q = q
        self.fromtime = fromtime

    def run(self):
        check_puzzle_from_queue(self.name, self.q, self.fromtime)
        debug_log(4, "Exiting puzzthread %s" % self.name)


def check_puzzle_from_queue(threadname, q, fromtime):
    while not exitFlag:
        queueLock.acquire()
        if not workQueue.empty():
            mypuzzle = q.get()
            queueLock.release()

            # puzzle-pull wait time per thread to avoid API limits
            time.sleep(config["BIGJIMMYBOT"]["PUZZLEPAUSETIME"])

            debug_log(
                4,
                "[Thread: %s] Fetched from queue puzzle: %s"
                % (threadname, mypuzzle["name"]),
            )

            # Feeble attempt to inject a new revision to split up grouping periodically
            # force_sheet_edit(mypuzzle['drive_id'])

            # Lots of annoying time string conversions here between mysql and google
            lastpuzzleacttime = datetime.datetime.fromordinal(1)
            myreq = "%s/puzzles/%s/lastact" % (config["BIGJIMMYBOT"]["APIURI"], mypuzzle["id"])
            responsestring = requests.get(myreq).text
            mypuzzleastact = json.loads(responsestring)["puzzle"]["lastact"]
            
            debug_log(0, "mypuzzlelastact pulled for puzzle %s as %s" % (mypuzzle["id"], str(mypuzzlelastact)))

            if mypuzzlelastact:
                lastpuzzleacttime = datetime.datetime.strptime(
                    mypuzzlelastact["time"], "%a, %d %b %Y %H:%M:%S %Z"
                )

            # Go through all revisions for the puzzle and see if any are relevant ("new")
            for revision in get_revisions(mypuzzle["drive_id"]):
                revisiontime = datetime.datetime.strptime(
                    revision["modifiedTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
                )

                if revisiontime > fromtime:
                    # This is a new revision since last loop, give or take a few minutes.
                    debug_log(
                        4,
                        "[Thread: %s] relatively recent revision found by %s on %s at %s"
                        % (
                            threadname,
                            revision["lastModifyingUser"]["emailAddress"],
                            mypuzzle["name"],
                            revision["modifiedTime"],
                        ),
                    )
                    debug_log(
                        4,
                        "[Thread: %s] previous last activity on this puzzle is %s"
                        % (threadname, lastpuzzleacttime),
                    )

                    if revisiontime > lastpuzzleacttime:
                        # This revision is newer than any other activity already associated with the puzzle
                        debug_log(
                            3,
                            "[Thread: %s] this is a newly discovered revision on puzzle id %s by %s! Adding to activity table."
                            % (
                                threadname,
                                mypuzzle["id"],
                                revision["lastModifyingUser"]["emailAddress"],
                            ),
                        )

                        mysolverid = solver_from_email(
                            revision["lastModifyingUser"]["emailAddress"]
                        )

                        if mysolverid == 0:
                            debug_log(
                                1,
                                "[Thread: %s] solver %s not found in solver db? This shouldn't happen. Skipping revision."
                                % (
                                    threadname,
                                    revision["lastModifyingUser"]["emailAddress"],
                                ),
                            )

                        if (
                            solver_from_email(
                                revision["lastModifyingUser"]["emailAddress"]
                            )
                            == 0
                        ):
                            debug_log(
                                1,
                                "[Thread: %s] solver %s not found in solver db? This shouldn't happen. Skipping revision."
                                % (
                                    threadname,
                                    revision["lastModifyingUser"]["emailAddress"],
                                ),
                            )
                            continue

                        # Fetch last activity (actually all info) for this solver PRIOR to this one. We'll use it in just a bit.
                        solverinfo = json.loads(
                            requests.get(
                                "%s/solvers/%s"
                                % (config["BIGJIMMYBOT"]["APIURI"], mysolverid)
                            ).text
                        )["solver"]

                        # Insert this activity into the activity DB for this puzzle/solver pair
                        databody = {
                            "lastact": {
                                "solver_id": "%s"
                                % solver_from_email(
                                    revision["lastModifyingUser"]["emailAddress"]
                                ),
                                "source": "google",
                                "type": "revise",
                            }
                        }
                        actupresponse = requests.post(
                            "%s/puzzles/%s/lastact"
                            % (config["BIGJIMMYBOT"]["APIURI"], mypuzzle["id"]),
                            json=databody,
                        )

                        debug_log(
                            4,
                            "[Thread: %s] Posted update %s to last activity for puzzle.  Response: %s"
                            % (threadname, databody, actupresponse.text),
                        )
                        debug_log(
                            4,
                            "[Thread: %s] Solver %s has current puzzle of %s"
                            % (threadname, mysolverid, solverinfo["puzz"]),
                        )

                        if solverinfo["puzz"] != mypuzzle["id"]:
                            # This potential solver is not currently on this puzzle. Interesting.
                            lastsolveracttime = datetime.datetime.strptime(
                                solverinfo["lastact"]["time"],
                                "%a, %d %b %Y %H:%M:%S %Z",
                            )
                            debug_log(
                                4,
                                "[Thread: %s] Last solver activity for %s was at %s"
                                % (threadname, solverinfo["name"], lastsolveracttime),
                            )
                            if config["BIGJIMMYBOT"]["AUTOASSIGN"] == "true":
                                if revisiontime > lastsolveracttime:
                                    debug_log(
                                        3,
                                        "[Thread: %s] Assigning solver %s to puzzle %s."
                                        % (threadname, mysolverid, mypuzzle["id"]),
                                    )

                                    databody = {"puzz": "%s" % mypuzzle["id"]}

                                    assignmentresponse = requests.post(
                                        "%s/solvers/%s/puzz"
                                        % (config["BIGJIMMYBOT"]["APIURI"], mysolverid),
                                        json=databody,
                                    )
                                    debug_log(
                                        4,
                                        "[Thread: %s] Posted %s to update current puzzle for solver %s.  Response: %s"
                                        % (
                                            threadname,
                                            databody,
                                            mysolverid,
                                            assignmentresponse.text,
                                        ),
                                    )
        else:
            queueLock.release()
    return 0


def solver_from_email(email):
    debug_log(4, "start. called with %s" % email)
    solverslist = json.loads(
        requests.get("%s/solvers" % config["BIGJIMMYBOT"]["APIURI"]).text
    )["solvers"]
    for solver in solverslist:
        if solver["name"].lower() == email.split("@")[0].lower():
            debug_log(4, "Solver %s is id: %s" % (email, solver["id"]))
            return solver["id"]
    return 0


if __name__ == "__main__":
    if initdrive() != 0:
        debug_log(0, "google drive init failed. Fatal.")
        sys.exit(255)

    debug_log(3, "google drive init succeeded. Hunt folder id: %s" % pblib.huntfolderid)

    while True:
        r = json.loads(requests.get("%s/all" % config["BIGJIMMYBOT"]["APIURI"]).text)
        debug_log(5, "api return: %s" % r)
        rounds = r["rounds"]
        debug_log(4, "loaded round list")
        puzzles = []
        for round in rounds:
            puzzlesinround = round["puzzles"]
            debug_log(
                4, "appending puzzles from round %s: %s" % (round["id"], puzzlesinround)
            )
            for puzzle in puzzlesinround:
                if puzzle["status"] != "Solved":
                    puzzles.append(puzzle)
                else:
                    debug_log(4, "skipping solved puzzle %s" % puzzle["name"])
        debug_log(4, "full puzzle structure loaded")
        fromtime = datetime.datetime.utcnow() - datetime.timedelta(seconds=30)
        debug_log(
            4,
            "Beginning iteration of bigjimmy bot across all puzzles (checking revs from time %s)"
            % fromtime,
        )

        # initialize threads
        for i in range(1, config["BIGJIMMYBOT"]["THREADCOUNT"] + 1):
            thread = puzzThread(threadID, i, workQueue, fromtime)
            thread.start()
            threads.append(thread)
            threadID += 1

        # put all puzzles in the queue so work can start
        queueLock.acquire()
        for puzzle in puzzles:
            workQueue.put(puzzle)
        queueLock.release()

        # wait for queue to be completed
        while not workQueue.empty():
            pass

        # Notify threads to exit
        exitFlag = 1

        # Wait for all threads to rejoin
        for t in threads:
            t.join()

        debug_log(
            4,
            "Completed iteration of bigjimmy bot across all puzzles from time %s"
            % fromtime,
        )
        exitFlag = 0
