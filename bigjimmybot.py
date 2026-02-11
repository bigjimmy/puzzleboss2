import sys
import pblib
import requests
import json
import time
import datetime
import threading
import queue
from pblib import *
from pbgooglelib import *
from pbdiscordlib import *

exitFlag = 0
queueLock = threading.Lock()
workQueue = queue.Queue(300)
threadID = 1
threads = []

# Loop iteration counter for Prometheus monitoring (resets on bot restart)
loop_iterations_total = 0


class puzzThread(threading.Thread):
    def __init__(self, threadID, name, q):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.q = q

    def run(self):
        check_puzzle_from_queue(self.name, self.q)
        debug_log(4, "Exiting puzzthread %s" % self.name)


def check_puzzle_from_queue(threadname, q):
    while not exitFlag:
        queueLock.acquire()
        if not workQueue.empty():
            mypuzzle = q.get()
            queueLock.release()

            # puzzle-pull wait time per thread to avoid API limits
            time.sleep(int(configstruct["BIGJIMMY_PUZZLEPAUSETIME"]))

            puzzle_start_time = time.time()
            debug_log(
                4,
                "[Thread: %s] Fetched from queue puzzle: %s"
                % (threadname, mypuzzle["name"]),
            )

            # Feeble attempt to inject a new revision to split up grouping periodically
            # force_sheet_edit(mypuzzle['drive_id'])

            # HYBRID APPROACH: Check sheetenabled to determine which method to use
            sheetenabled = mypuzzle.get("sheetenabled", 0)

            if sheetenabled == 1:
                # Sheet has add-on enabled, use the hidden sheet approach
                debug_log(
                    4,
                    "[Thread: %s] Using hidden sheet tracking for %s (sheetenabled=1)"
                    % (threadname, mypuzzle["name"]),
                )
                sheet_info = get_puzzle_sheet_info_activity(
                    mypuzzle["drive_id"], mypuzzle["name"]
                )
            else:
                # Check if hidden _pb_activity sheet exists (add-on deployed but not marked)
                debug_log(
                    4,
                    "[Thread: %s] Checking for hidden activity sheet on %s (sheetenabled=0)"
                    % (threadname, mypuzzle["name"]),
                )
                # Try to read hidden sheet - if it exists and has data, enable sheetenabled
                test_info = get_puzzle_sheet_info_activity(
                    mypuzzle["drive_id"], mypuzzle["name"]
                )
                if test_info.get("editors"):
                    # Hidden sheet found with activity! Enable sheetenabled and use the data
                    debug_log(
                        3,
                        "[Thread: %s] Hidden activity sheet found on %s, enabling sheetenabled"
                        % (threadname, mypuzzle["name"]),
                    )
                    try:
                        requests.post(
                            f"{config['API']['APIURI']}/puzzles/{mypuzzle['id']}/sheetenabled",
                            json={"sheetenabled": 1},
                        )
                        # Use the data we just fetched and update local flag
                        sheet_info = test_info
                        sheetenabled = 1  # Update local variable so later processing uses correct path
                    except Exception as e:
                        debug_log(
                            1,
                            "[Thread: %s] Error enabling sheetenabled: %s"
                            % (threadname, e),
                        )
                        # Fall back to legacy if update failed
                        sheet_info = get_puzzle_sheet_info_legacy(
                            mypuzzle["drive_id"], mypuzzle["name"]
                        )
                else:
                    # No hidden sheet found, use legacy approach
                    debug_log(
                        4,
                        "[Thread: %s] No add-on on %s, using legacy Revisions API"
                        % (threadname, mypuzzle["name"]),
                    )
                    sheet_info = get_puzzle_sheet_info_legacy(
                        mypuzzle["drive_id"], mypuzzle["name"]
                    )

            # Update sheet count only if changed
            if sheet_info["sheetcount"] is not None and sheet_info[
                "sheetcount"
            ] != mypuzzle.get("sheetcount"):
                debug_log(
                    4,
                    "[Thread: %s] Updating sheetcount for %s: %s -> %s"
                    % (
                        threadname,
                        mypuzzle["name"],
                        mypuzzle.get("sheetcount"),
                        sheet_info["sheetcount"],
                    ),
                )
                try:
                    requests.post(
                        f"{config['API']['APIURI']}/puzzles/{mypuzzle['id']}/sheetcount",
                        json={"sheetcount": sheet_info["sheetcount"]},
                    )
                except Exception as e:
                    debug_log(
                        1,
                        "[Thread: %s] Error updating sheetcount: %s" % (threadname, e),
                    )

            # Fetch last sheet activity for this puzzle to compare against editor timestamps
            myreq = f"{config['API']['APIURI']}/puzzles/{mypuzzle['id']}/lastsheetact"
            try:
                responsestring = requests.get(myreq).text
            except Exception as e:
                debug_log(
                    1,
                    "Error fetching puzzle info from puzzleboss. Puzzleboss down?: %s"
                    % e,
                )
                time.sleep(int(configstruct["BIGJIMMY_PUZZLEPAUSETIME"]))
                continue

            try:
                response_json = json.loads(responsestring)
                if "error" in response_json:
                    debug_log(
                        2,
                        "[Thread: %s] API error for puzzle %s: %s"
                        % (threadname, mypuzzle["id"], response_json.get("error")),
                    )
                    continue
                mypuzzlelastsheetact = response_json["puzzle"]["lastsheetact"]
            except Exception as e:
                debug_log(
                    1,
                    "Error interpreting puzzle info from puzzleboss. Response: %s, Error: %s"
                    % (responsestring[:200], e),
                )
                time.sleep(int(configstruct["BIGJIMMY_PUZZLEPAUSETIME"]))
                continue

            debug_log(
                5,
                "mypuzzlelastsheetact pulled for puzzle %s as %s"
                % (mypuzzle["id"], str(mypuzzlelastsheetact)),
            )

            if sheetenabled == 1:
                # HIDDEN SHEET APPROACH: Compare unix timestamps
                lastsheetact_ts = 0
                if mypuzzlelastsheetact:
                    lastsheetacttime = datetime.datetime.strptime(
                        mypuzzlelastsheetact["time"], "%a, %d %b %Y %H:%M:%S %Z"
                    )
                    lastsheetact_ts = lastsheetacttime.timestamp()

                # Go through all editors from hidden sheet and see if any are newer than lastsheetact
                for editor in sheet_info["editors"]:
                    solvername = editor["solvername"]
                    edit_ts = editor["timestamp"]  # Unix timestamp

                    # Skip bot's own activity silently
                    if solvername.lower() == "bigjimmy":
                        debug_log(
                            5,
                            "[Thread: %s] Skipping bot's own activity on %s"
                            % (threadname, mypuzzle["name"]),
                        )
                        continue

                    if edit_ts > lastsheetact_ts:
                        # This edit is newer than the last recorded sheet activity
                        debug_log(
                            3,
                            "[Thread: %s] New edit on puzzle %s by %s at %s (last sheet activity was %s)"
                            % (
                                threadname,
                                mypuzzle["name"],
                                solvername,
                                datetime.datetime.fromtimestamp(edit_ts),
                                datetime.datetime.fromtimestamp(lastsheetact_ts)
                                if lastsheetact_ts
                                else "never",
                            ),
                        )

                        mysolverid = solver_from_name(solvername)

                        if mysolverid == 0:
                            debug_log(
                                2,
                                "[Thread: %s] solver %s not found in solver db. Skipping."
                                % (threadname, solvername),
                            )
                            continue

                        # Fetch last activity (actually all info) for this solver PRIOR to this one
                        solverinfo = json.loads(
                            requests.get(
                                f"{config['API']['APIURI']}/solvers/{mysolverid}"
                            ).text
                        )["solver"]

                        # Always record activity, even if solver is already on puzzle
                        databody = {
                            "lastact": {
                                "solver_id": str(mysolverid),
                                "source": "bigjimmybot",
                                "type": "revise",
                            }
                        }
                        actupresponse = requests.post(
                            f"{config['API']['APIURI']}/puzzles/{mypuzzle['id']}/lastact",
                            json=databody,
                        )

                        debug_log(
                            4,
                            "[Thread: %s] Posted update %s to last activity for puzzle.  Response: %s"
                            % (threadname, databody, actupresponse.text),
                        )

                        # Only auto-assign if solver is not already on this puzzle
                        if solverinfo["puzz"] != mypuzzle["name"]:
                            # This potential solver is not currently on this puzzle
                            if not solverinfo["lastact"]:
                                lastsolveract_ts = 0
                            else:
                                lastsolveracttime = datetime.datetime.strptime(
                                    solverinfo["lastact"]["time"],
                                    "%a, %d %b %Y %H:%M:%S %Z",
                                )
                                lastsolveract_ts = lastsolveracttime.timestamp()
                            debug_log(
                                4,
                                "[Thread: %s] Last solver activity for %s was at %s"
                                % (
                                    threadname,
                                    solverinfo["name"],
                                    datetime.datetime.fromtimestamp(lastsolveract_ts)
                                    if lastsolveract_ts
                                    else "never",
                                ),
                            )
                            if configstruct["BIGJIMMY_AUTOASSIGN"] == "true":
                                if edit_ts > lastsolveract_ts:
                                    debug_log(
                                        3,
                                        "[Thread: %s] Assigning solver %s to puzzle %s."
                                        % (threadname, mysolverid, mypuzzle["id"]),
                                    )

                                    databody = {"puzz": str(mypuzzle["id"])}

                                    assignmentresponse = requests.post(
                                        f"{config['API']['APIURI']}/solvers/{mysolverid}/puzz",
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
                # LEGACY REVISIONS API APPROACH: Compare datetime objects
                lastsheetacttime = datetime.datetime.fromordinal(1)
                if mypuzzlelastsheetact:
                    lastsheetacttime = datetime.datetime.strptime(
                        mypuzzlelastsheetact["time"], "%a, %d %b %Y %H:%M:%S %Z"
                    )

                # Go through all revisions and see if any are newer than lastsheetact
                for revision in sheet_info["revisions"]:
                    revisiontime = datetime.datetime.strptime(
                        revision["modifiedTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
                    )

                    if revisiontime > lastsheetacttime:
                        # This revision is newer than the last recorded sheet activity
                        debug_log(
                            3,
                            "[Thread: %s] New revision on puzzle %s by %s at %s (last sheet activity was %s)"
                            % (
                                threadname,
                                mypuzzle["name"],
                                revision["lastModifyingUser"]["emailAddress"],
                                revision["modifiedTime"],
                                lastsheetacttime,
                            ),
                        )

                        mysolverid = solver_from_email(
                            revision["lastModifyingUser"]["emailAddress"]
                        )

                        if mysolverid == 0:
                            debug_log(
                                2,
                                "[Thread: %s] solver %s not found in solver db. Skipping."
                                % (
                                    threadname,
                                    revision["lastModifyingUser"]["emailAddress"],
                                ),
                            )
                            continue

                        # Fetch last activity (actually all info) for this solver
                        solverinfo = json.loads(
                            requests.get(
                                f"{config['API']['APIURI']}/solvers/{mysolverid}"
                            ).text
                        )["solver"]

                        # Always record activity, even if solver is already on puzzle
                        databody = {
                            "lastact": {
                                "solver_id": str(mysolverid),
                                "source": "bigjimmybot",
                                "type": "revise",
                            }
                        }
                        actupresponse = requests.post(
                            f"{config['API']['APIURI']}/puzzles/{mypuzzle['id']}/lastact",
                            json=databody,
                        )

                        debug_log(
                            4,
                            "[Thread: %s] Posted update %s to last activity for puzzle.  Response: %s"
                            % (threadname, databody, actupresponse.text),
                        )

                        # Only auto-assign if solver is not already on this puzzle
                        if solverinfo["puzz"] != mypuzzle["name"]:
                            if not solverinfo["lastact"]:
                                lastsolveract_ts = 0
                            else:
                                lastsolveracttime = datetime.datetime.strptime(
                                    solverinfo["lastact"]["time"],
                                    "%a, %d %b %Y %H:%M:%S %Z",
                                )
                                lastsolveract_ts = lastsolveracttime.timestamp()
                            debug_log(
                                4,
                                "[Thread: %s] Last solver activity for %s was at %s"
                                % (
                                    threadname,
                                    solverinfo["name"],
                                    datetime.datetime.fromtimestamp(lastsolveract_ts)
                                    if lastsolveract_ts
                                    else "never",
                                ),
                            )
                            if configstruct["BIGJIMMY_AUTOASSIGN"] == "true":
                                revision_ts = revisiontime.timestamp()
                                if revision_ts > lastsolveract_ts:
                                    debug_log(
                                        3,
                                        "[Thread: %s] Assigning solver %s to puzzle %s."
                                        % (threadname, mysolverid, mypuzzle["id"]),
                                    )

                                    databody = {"puzz": str(mypuzzle["id"])}

                                    assignmentresponse = requests.post(
                                        f"{config['API']['APIURI']}/solvers/{mysolverid}/puzz",
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

            # Check for abandoned puzzles: "Being worked" with no solvers and no recent activity
            # This check happens AFTER sheet activity detection to ensure new activity is recorded first
            # Note: Speculative puzzles are excluded (they have status "Speculative", not "Being worked")
            if mypuzzle.get("status") == "Being worked":
                cursolvers = mypuzzle.get("cursolvers")
                if not cursolvers or not cursolvers.strip():
                    # No current solvers, check if any activity (sheet edits, comments, assignments, tags) is stale
                    abandoned_timeout_minutes = int(
                        configstruct.get("BIGJIMMY_ABANDONED_TIMEOUT_MINUTES", 10)
                    )
                    abandoned_timeout_seconds = abandoned_timeout_minutes * 60
                    abandoned_status = configstruct.get(
                        "BIGJIMMY_ABANDONED_STATUS", "Abandoned"
                    )

                    # Fetch lastact (any activity type - superset of lastsheetact)
                    lastact = None
                    try:
                        lastact_response = requests.get(
                            f"{config['API']['APIURI']}/puzzles/{mypuzzle['id']}/lastact"
                        )
                        lastact_data = json.loads(lastact_response.text)
                        lastact = lastact_data.get("lastact")
                    except Exception as e:
                        debug_log(
                            2,
                            "[Thread: %s] Error fetching lastact for %s: %s"
                            % (threadname, mypuzzle["name"], e),
                        )

                    is_abandoned = False
                    if not lastact or not lastact.get("time"):
                        # No activity recorded at all - this shouldn't happen after we just checked
                        # for sheet activity above, but if it does, don't mark as abandoned yet.
                        # Wait for the next cycle to check again.
                        debug_log(
                            4,
                            "[Thread: %s] Puzzle %s has no activity yet, will check again next cycle"
                            % (threadname, mypuzzle["name"]),
                        )
                    else:
                        try:
                            lastact_time = datetime.datetime.strptime(
                                lastact["time"], "%a, %d %b %Y %H:%M:%S %Z"
                            )
                            now = datetime.datetime.utcnow()
                            time_since_activity = (now - lastact_time).total_seconds()

                            if time_since_activity > abandoned_timeout_seconds:
                                is_abandoned = True
                                debug_log(
                                    3,
                                    "[Thread: %s] Puzzle %s inactive for %.1f min (threshold: %d), no solvers"
                                    % (
                                        threadname,
                                        mypuzzle["name"],
                                        time_since_activity / 60,
                                        abandoned_timeout_minutes,
                                    ),
                                )
                        except Exception as e:
                            debug_log(
                                2,
                                "[Thread: %s] Error parsing lastact time for %s: %s"
                                % (threadname, mypuzzle["name"], e),
                            )

                    if is_abandoned:
                        try:
                            requests.post(
                                f"{config['API']['APIURI']}/puzzles/{mypuzzle['id']}/status",
                                json={"status": abandoned_status},
                            )
                            debug_log(
                                3,
                                "[Thread: %s] Set puzzle %s status to '%s'"
                                % (threadname, mypuzzle["name"], abandoned_status),
                            )
                        except Exception as e:
                            debug_log(
                                1,
                                "[Thread: %s] Error updating status for %s: %s"
                                % (threadname, mypuzzle["name"], e),
                            )

            # Log per-puzzle timing
            puzzle_elapsed = time.time() - puzzle_start_time
            debug_log(
                4,
                "[Thread: %s] Finished processing puzzle %s in %.2f seconds"
                % (threadname, mypuzzle["name"], puzzle_elapsed),
            )
        else:
            queueLock.release()
    return 0


def solver_from_email(email):
    """Look up solver ID by email address (extracts username from email)."""
    debug_log(4, "start. called with %s" % email)
    solverslist = json.loads(requests.get(f"{config['API']['APIURI']}/solvers").text)[
        "solvers"
    ]
    for solver in solverslist:
        if solver["name"].lower() == email.split("@")[0].lower():
            debug_log(4, "Solver %s is id: %s" % (email, solver["id"]))
            return solver["id"]
    return 0


def solver_from_name(name):
    """Look up solver ID by solver name directly."""
    debug_log(4, "start. called with %s" % name)
    solverslist = json.loads(requests.get(f"{config['API']['APIURI']}/solvers").text)[
        "solvers"
    ]
    for solver in solverslist:
        if solver["name"].lower() == name.lower():
            debug_log(4, "Solver %s is id: %s" % (name, solver["id"]))
            return solver["id"]
    return 0


if __name__ == "__main__":
    if initdrive() != 0:
        debug_log(0, "google drive init failed. Fatal.")
        sys.exit(255)

    debug_log(3, "google drive init succeeded. Hunt folder id: %s" % pblib.huntfolderid)

    while True:
        # Reload config from database each loop to pick up changes
        try:
            refresh_config()
            debug_log(5, "Config reloaded from database")
        except Exception as e:
            debug_log(1, "Error refreshing config: %s" % e)

        # Increment and post loop iteration counter early (before SKIP_GOOGLE_API check)
        # This ensures the counter increments even when Google API is disabled
        loop_iterations_total += 1
        try:
            requests.post(
                f"{config['API']['APIURI']}/botstats/loop_iterations_total",
                json={"val": str(loop_iterations_total)},
            )
        except Exception as e:
            debug_log(2, "Error posting loop iteration counter: %s" % e)

        # If Google API is disabled, just sleep and loop
        if configstruct.get("SKIP_GOOGLE_API", "false") == "true":
            debug_log(3, "SKIP_GOOGLE_API is true, sleeping 5 seconds")
            time.sleep(5)
            continue

        # Start timing setup phase
        setup_start_time = time.time()

        try:
            r = json.loads(requests.get(f"{config['API']['APIURI']}/all").text)
        except Exception as e:
            debug_log(
                1,
                "Error fetching puzzle info from puzzleboss. Puzzleboss down?: %s" % e,
            )
            time.sleep(int(configstruct["BIGJIMMY_PUZZLEPAUSETIME"]))
            continue

        debug_log(5, "api return: %s" % r)
        rounds = r["rounds"]
        debug_log(4, "loaded round list")
        puzzles = []
        for rnd in rounds:
            puzzlesinround = rnd["puzzles"]
            debug_log(
                4, "appending puzzles from round %s: %s" % (rnd["id"], puzzlesinround)
            )
            for puzzle in puzzlesinround:
                if puzzle["status"] != "Solved":
                    puzzles.append(puzzle)
                else:
                    debug_log(4, "skipping solved puzzle %s" % puzzle["name"])
        debug_log(4, "full puzzle structure loaded")

        # initialize threads
        for i in range(1, (int(configstruct["BIGJIMMY_THREADCOUNT"]) + 1)):
            thread = puzzThread(threadID, i, workQueue)
            thread.start()
            threads.append(thread)
            threadID += 1

        # put all puzzles in the queue so work can start
        queueLock.acquire()
        for puzzle in puzzles:
            workQueue.put(puzzle)
        queueLock.release()

        # Setup complete, start timing processing phase
        setup_elapsed = time.time() - setup_start_time
        processing_start_time = time.time()
        debug_log(
            4,
            "Beginning iteration of bigjimmy bot across all puzzles (setup took %.2f sec)"
            % setup_elapsed,
        )

        # wait for queue to be completed
        while not workQueue.empty():
            pass

        # Notify threads to exit
        exitFlag = 1

        # Wait for all threads to rejoin
        for t in threads:
            t.join()

        processing_elapsed = time.time() - processing_start_time
        loop_elapsed = setup_elapsed + processing_elapsed
        debug_log(
            4,
            "Completed iteration of bigjimmy bot across all puzzles",
        )
        debug_log(
            3,
            "Full iteration completed: %d puzzles in %.2f sec (setup: %.2f sec, processing: %.2f sec, %.2f sec/puzzle avg)"
            % (
                len(puzzles),
                loop_elapsed,
                setup_elapsed,
                processing_elapsed,
                processing_elapsed / len(puzzles) if puzzles else 0,
            ),
        )

        # Post timing stats to API for Prometheus metrics
        try:
            requests.post(
                f"{config['API']['APIURI']}/botstats/loop_time_seconds",
                json={"val": f"{loop_elapsed:.2f}"},
            )
            requests.post(
                f"{config['API']['APIURI']}/botstats/loop_setup_seconds",
                json={"val": f"{setup_elapsed:.2f}"},
            )
            requests.post(
                f"{config['API']['APIURI']}/botstats/loop_processing_seconds",
                json={"val": f"{processing_elapsed:.2f}"},
            )
            requests.post(
                f"{config['API']['APIURI']}/botstats/loop_puzzle_count",
                json={"val": str(len(puzzles))},
            )
            if puzzles:
                requests.post(
                    f"{config['API']['APIURI']}/botstats/loop_avg_seconds_per_puzzle",
                    json={"val": f"{processing_elapsed / len(puzzles):.2f}"},
                )
            # Post quota failure count (cumulative counter, not reset)
            quota_failures = get_quota_failure_count()
            requests.post(
                f"{config['API']['APIURI']}/botstats/quota_failures",
                json={"val": str(quota_failures)},
            )
        except Exception as e:
            debug_log(1, "Error posting botstats: %s" % e)

        exitFlag = 0
