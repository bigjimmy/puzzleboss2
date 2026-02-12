"""
BigJimmy Bot - Sheet activity tracking and solver assignment.

This bot monitors Google Sheets for puzzle-solving activity and automatically
assigns solvers to puzzles based on their edits. Supports both modern hidden
sheet tracking (via Apps Script) and legacy Revisions API tracking.
"""

import sys
import json
import time
import datetime
import threading
import queue
from typing import Optional, Dict, Any, List

import requests

# Explicit imports instead of wildcard
from pblib import debug_log, config, configstruct, refresh_config
from pbgooglelib import (
    get_puzzle_sheet_info_activity,
    get_puzzle_sheet_info_legacy,
    activate_puzzle_sheet_via_api,
    get_quota_failure_count,
    initdrive,
)
import pblib

# Module-level constants and state
EXIT_FLAG = 0
QUEUE_LOCK = threading.Lock()
WORK_QUEUE = queue.Queue(300)
THREAD_COUNTER = 0
THREADS = []
LOOP_ITERATIONS_TOTAL = 0


# ── HTTP & API Helpers ──────────────────────────────────────────────────


def _api_request_with_retry(
    method: str, url: str, max_retries: int = 3, timeout: int = 10, **kwargs
) -> Optional[requests.Response]:
    """
    Wrapper for requests.get/post with timeout and exponential backoff retry.

    Args:
        method: 'get' or 'post'
        url: API endpoint URL
        max_retries: Number of retry attempts (default 3)
        timeout: Request timeout in seconds (default 10)
        **kwargs: Additional arguments passed to requests (json, headers, etc.)

    Returns:
        requests.Response object on success, None on total failure
    """
    for attempt in range(max_retries):
        try:
            if method.lower() == "get":
                response = requests.get(url, timeout=timeout, **kwargs)
            elif method.lower() == "post":
                response = requests.post(url, timeout=timeout, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")

            return response

        except requests.exceptions.Timeout:
            delay = 2**attempt  # Exponential backoff: 1s, 2s, 4s
            debug_log(
                2,
                f"API timeout (attempt {attempt + 1}/{max_retries}): {url} - retrying in {delay}s",
            )
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                debug_log(1, f"API timeout after {max_retries} attempts: {url}")
                return None

        except requests.exceptions.RequestException as e:
            delay = 2**attempt
            debug_log(
                2,
                f"API request error (attempt {attempt + 1}/{max_retries}): {url} - {e}",
            )
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                debug_log(
                    1, f"API request failed after {max_retries} attempts: {url} - {e}"
                )
                return None

    return None




# ── Solver Lookup ───────────────────────────────────────────────────────


def _get_solver_id(identifier: str, match_type: str = "name") -> int:
    """
    Look up solver ID by name or email.

    Args:
        identifier: Solver name or email address
        match_type: 'name' for direct name match, 'email' to extract username from email

    Returns:
        Solver ID on success, 0 if not found
    """
    debug_log(4, f"Looking up solver by {match_type}: {identifier}")
    response = _api_request_with_retry("get", f"{config['API']['APIURI']}/solvers")
    if not response:
        debug_log(2, "Failed to fetch solvers list after retries")
        return 0

    solvers_list = json.loads(response.text)["solvers"]
    for solver in solvers_list:
        if match_type == "email":
            username = identifier.split("@")[0].lower()
            if solver["name"].lower() == username:
                debug_log(4, f"Solver {identifier} is id: {solver['id']}")
                return solver["id"]
        else:  # name
            if solver["name"].lower() == identifier.lower():
                debug_log(4, f"Solver {identifier} is id: {solver['id']}")
                return solver["id"]
    return 0




# ── Timestamp Parsing ───────────────────────────────────────────────────


def _parse_api_timestamp(timestamp_str: str) -> float:
    """
    Parse API timestamp string to Unix timestamp.

    Args:
        timestamp_str: Timestamp in format "Day, DD Mon YYYY HH:MM:SS TZ"

    Returns:
        Unix timestamp as float
    """
    dt = datetime.datetime.strptime(timestamp_str, "%a, %d %b %Y %H:%M:%S %Z")
    return dt.timestamp()


def _parse_revision_timestamp(revision_time: str) -> float:
    """
    Parse Google Revisions API timestamp to Unix timestamp.

    Args:
        revision_time: ISO format "YYYY-MM-DDTHH:MM:SS.fffZ"

    Returns:
        Unix timestamp as float
    """
    dt = datetime.datetime.strptime(revision_time, "%Y-%m-%dT%H:%M:%S.%fZ")
    return dt.timestamp()




# ── Activity Recording ──────────────────────────────────────────────────


def _record_solver_activity(
    puzzle_id: int, solver_id: int, threadname: str
) -> Optional[requests.Response]:
    """
    Record solver activity on a puzzle.

    Args:
        puzzle_id: Puzzle database ID
        solver_id: Solver database ID
        threadname: Name of worker thread (for logging)

    Returns:
        Response object on success, None on failure
    """
    activity_data = {
        "lastact": {
            "solver_id": str(solver_id),
            "source": "bigjimmybot",
            "type": "revise",
        }
    }
    response = _api_request_with_retry(
        "post",
        f"{config['API']['APIURI']}/puzzles/{puzzle_id}/lastact",
        json=activity_data,
    )

    if response:
        debug_log(
            4,
            f"[Thread: {threadname}] Posted activity update for puzzle {puzzle_id}, solver {solver_id}. Response: {response.text}",
        )
    else:
        debug_log(
            2, f"[Thread: {threadname}] Failed to post activity update after retries"
        )

    return response


def _assign_solver_to_puzzle(
    puzzle_id: int, solver_id: int, threadname: str
) -> Optional[requests.Response]:
    """
    Assign a solver to a puzzle.

    Args:
        puzzle_id: Puzzle database ID
        solver_id: Solver database ID
        threadname: Name of worker thread (for logging)

    Returns:
        Response object on success, None on failure
    """
    assignment_data = {"puzz": str(puzzle_id)}
    response = _api_request_with_retry(
        "post",
        f"{config['API']['APIURI']}/solvers/{solver_id}/puzz",
        json=assignment_data,
    )

    if response:
        debug_log(
            4,
            f"[Thread: {threadname}] Assigned solver {solver_id} to puzzle {puzzle_id}. Response: {response.text}",
        )
    else:
        debug_log(
            2,
            f"[Thread: {threadname}] Failed to assign solver after retries",
        )

    return response




# ── Activity Processing ─────────────────────────────────────────────────


def _process_activity_records(
    records: List[Dict[str, Any]],
    puzzle: Dict[str, Any],
    last_sheet_act_ts: float,
    threadname: str,
    use_hidden_sheet: bool,
) -> None:
    """
    Process activity records from either hidden sheet or Revisions API.

    This is the core logic for detecting new edits, recording activity,
    and auto-assigning solvers. Works with both tracking methods.

    Args:
        records: List of editor records (hidden sheet) or revision records (legacy)
        puzzle: Puzzle dictionary from API
        last_sheet_act_ts: Last recorded sheet activity timestamp (Unix)
        threadname: Name of worker thread (for logging)
        use_hidden_sheet: True for hidden sheet format, False for revisions format
    """
    debug_log(
        5,
        f"[Thread: {threadname}] _process_activity_records called for {puzzle['name']} with {len(records)} records"
    )

    for record in records:
        # Normalize differences between hidden sheet and revisions formats
        if use_hidden_sheet:
            identifier = record["solvername"]
            edit_ts = record["timestamp"]  # Already Unix timestamp
            match_type = "name"
        else:
            identifier = record["lastModifyingUser"]["emailAddress"]
            edit_ts = _parse_revision_timestamp(record["modifiedTime"])
            match_type = "email"

        debug_log(
            5,
            f"[Thread: {threadname}] Processing record for {identifier} at {edit_ts}"
        )

        # Skip bot's own activity
        if use_hidden_sheet and identifier.lower() == "bigjimmy":
            debug_log(
                5, f"[Thread: {threadname}] Skipping bot's own activity on {puzzle['name']}"
            )
            continue

        # Check if this edit is newer than last recorded activity
        if edit_ts <= last_sheet_act_ts:
            continue

        # New activity detected!
        debug_log(
            3,
            f"[Thread: {threadname}] New edit on puzzle {puzzle['name']} by {identifier} "
            f"at {datetime.datetime.fromtimestamp(edit_ts)} "
            f"(last sheet activity was {datetime.datetime.fromtimestamp(last_sheet_act_ts) if last_sheet_act_ts else 'never'})",
        )

        # Look up solver ID
        solver_id = _get_solver_id(identifier, match_type)
        if solver_id == 0:
            debug_log(
                2,
                f"[Thread: {threadname}] solver {identifier} not found in solver db. Skipping.",
            )
            continue

        # Fetch solver info to check current assignment
        solver_response = _api_request_with_retry(
            "get", f"{config['API']['APIURI']}/solvers/{solver_id}"
        )
        if not solver_response:
            debug_log(
                2,
                f"[Thread: {threadname}] Failed to fetch solver info for {solver_id} after retries",
            )
            continue

        solver_info = json.loads(solver_response.text)["solver"]

        # Always record activity, even if solver is already on puzzle
        _record_solver_activity(puzzle["id"], solver_id, threadname)

        # Only auto-assign if solver is not already on this puzzle
        if solver_info["puzz"] == puzzle["name"]:
            debug_log(
                4,
                f"[Thread: {threadname}] Solver {solver_info['name']} already assigned to {puzzle['name']}, skipping auto-assign"
            )
            continue

        # Check if edit is newer than solver's last activity
        if not solver_info["lastact"]:
            last_solver_act_ts = 0
        else:
            last_solver_act_ts = _parse_api_timestamp(solver_info["lastact"]["time"])

        debug_log(
            4,
            f"[Thread: {threadname}] Edit at {datetime.datetime.fromtimestamp(edit_ts)}, "
            f"solver {solver_info['name']} last activity at {datetime.datetime.fromtimestamp(last_solver_act_ts) if last_solver_act_ts else 'never'}"
        )

        # Auto-assign if enabled and edit is newer than solver's last activity
        if configstruct["BIGJIMMY_AUTOASSIGN"] != "true":
            debug_log(
                4,
                f"[Thread: {threadname}] Auto-assign disabled (BIGJIMMY_AUTOASSIGN={configstruct.get('BIGJIMMY_AUTOASSIGN', 'not set')})"
            )
        elif edit_ts <= last_solver_act_ts:
            debug_log(
                4,
                f"[Thread: {threadname}] Edit timestamp {edit_ts} <= solver's last activity {last_solver_act_ts}, not auto-assigning"
            )
        else:
            debug_log(
                3,
                f"[Thread: {threadname}] Auto-assigning solver {solver_id} ({solver_info['name']}) to puzzle {puzzle['id']} ({puzzle['name']})"
            )
            _assign_solver_to_puzzle(puzzle["id"], solver_id, threadname)




# ── Sheet Info & Metadata ───────────────────────────────────────────────


def _fetch_sheet_info(
    puzzle: Dict[str, Any], threadname: str
) -> tuple[Dict[str, Any], int]:
    """
    Fetch sheet information using appropriate method (hidden sheet or legacy).

    Attempts to activate add-on if not yet enabled.

    Args:
        puzzle: Puzzle dictionary from API
        threadname: Name of worker thread (for logging)

    Returns:
        Tuple of (sheet_info dict, sheetenabled flag)
    """
    sheetenabled = puzzle.get("sheetenabled", 0)

    if sheetenabled == 1:
        # Sheet has add-on enabled, use the hidden sheet approach
        debug_log(
            4,
            f"[Thread: {threadname}] Using hidden sheet tracking for {puzzle['name']} (sheetenabled=1)",
        )
        sheet_info = get_puzzle_sheet_info_activity(puzzle["drive_id"], puzzle["name"])
        return sheet_info, 1

    # No add-on deployed yet - try to activate it
    debug_log(
        3,
        f"[Thread: {threadname}] Attempting to activate add-on on {puzzle['name']} (sheetenabled=0)",
    )

    activation_success = False
    try:
        activation_success = activate_puzzle_sheet_via_api(
            puzzle["drive_id"], puzzle["name"]
        )
    except Exception as e:
        debug_log(
            2,
            f"[Thread: {threadname}] Add-on activation failed for {puzzle['name']}: {e}",
        )

    if activation_success:
        # Activation succeeded! Set sheetenabled=1 and use hidden sheet approach
        debug_log(
            3,
            f"[Thread: {threadname}] Add-on activated successfully on {puzzle['name']}, enabling sheetenabled",
        )
        response = _api_request_with_retry(
            "post",
            f"{config['API']['APIURI']}/puzzles/{puzzle['id']}/sheetenabled",
            json={"sheetenabled": 1},
        )
        if response:
            sheet_info = get_puzzle_sheet_info_activity(
                puzzle["drive_id"], puzzle["name"]
            )
            return sheet_info, 1
        else:
            debug_log(
                2,
                f"[Thread: {threadname}] Failed to update sheetenabled in DB, falling back to legacy",
            )

    # Activation failed or DB update failed, fall back to legacy Revisions API
    debug_log(
        4,
        f"[Thread: {threadname}] Using legacy Revisions API for {puzzle['name']} (activation not available)",
    )
    sheet_info = get_puzzle_sheet_info_legacy(puzzle["drive_id"], puzzle["name"])
    return sheet_info, 0


def _update_sheet_count(
    puzzle: Dict[str, Any], sheet_info: Dict[str, Any], threadname: str
) -> None:
    """
    Update puzzle sheet count if changed.

    Args:
        puzzle: Puzzle dictionary from API
        sheet_info: Sheet info from Google API
        threadname: Name of worker thread (for logging)
    """
    if (
        sheet_info["sheetcount"] is not None
        and sheet_info["sheetcount"] != puzzle.get("sheetcount")
    ):
        debug_log(
            4,
            f"[Thread: {threadname}] Updating sheetcount for {puzzle['name']}: "
            f"{puzzle.get('sheetcount')} -> {sheet_info['sheetcount']}",
        )
        response = _api_request_with_retry(
            "post",
            f"{config['API']['APIURI']}/puzzles/{puzzle['id']}/sheetcount",
            json={"sheetcount": sheet_info["sheetcount"]},
        )
        if not response:
            debug_log(
                1,
                f"[Thread: {threadname}] Failed to update sheetcount after retries",
            )


def _fetch_last_sheet_activity(
    puzzle: Dict[str, Any], threadname: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch last sheet activity timestamp for puzzle.

    Args:
        puzzle: Puzzle dictionary from API
        threadname: Name of worker thread (for logging)

    Returns:
        lastsheetact dict from API, or None if fetch failed
    """
    debug_log(
        5,
        f"[Thread: {threadname}] Fetching lastsheetact for puzzle {puzzle['id']} ({puzzle['name']})"
    )
    url = f"{config['API']['APIURI']}/puzzles/{puzzle['id']}/lastsheetact"
    response = _api_request_with_retry("get", url)
    if not response:
        debug_log(
            1,
            "Error fetching puzzle info from puzzleboss after retries. Puzzleboss down?",
        )
        return None

    try:
        response_json = json.loads(response.text)
        if "error" in response_json:
            debug_log(
                2,
                f"[Thread: {threadname}] API error for puzzle {puzzle['id']}: {response_json.get('error')}",
            )
            return None
        lastsheetact = response_json["puzzle"]["lastsheetact"]
        debug_log(
            5,
            f"[Thread: {threadname}] Fetched lastsheetact for {puzzle['name']}: {lastsheetact}"
        )
        return lastsheetact
    except Exception as e:
        debug_log(
            1,
            f"[Thread: {threadname}] Error parsing lastsheetact response for {puzzle['name']}: {e}, Response: {response.text[:200]}",
        )
        return None


def _process_sheet_activity(
    puzzle: Dict[str, Any], sheet_info: Dict[str, Any], sheetenabled: int, threadname: str
) -> None:
    """
    Process sheet activity and update solver assignments.

    Args:
        puzzle: Puzzle dictionary from API
        sheet_info: Sheet info from Google API
        sheetenabled: 1 for hidden sheet, 0 for legacy
        threadname: Name of worker thread (for logging)
    """
    # Fetch last sheet activity for this puzzle
    last_sheet_act = _fetch_last_sheet_activity(puzzle, threadname)
    if last_sheet_act is None:
        debug_log(
            2,
            f"[Thread: {threadname}] Skipping activity processing for {puzzle['name']} - failed to fetch lastsheetact"
        )
        return

    debug_log(
        5,
        f"mypuzzlelastsheetact pulled for puzzle {puzzle['id']} as {str(last_sheet_act)}",
    )

    # Convert to Unix timestamp for comparison
    last_sheet_act_ts = 0
    if last_sheet_act:
        last_sheet_act_ts = _parse_api_timestamp(last_sheet_act["time"])

    # Process activity records using unified function
    if sheetenabled == 1:
        # Hidden sheet approach
        records = sheet_info.get("editors", [])
        debug_log(
            4,
            f"[Thread: {threadname}] Processing {len(records)} editor records from hidden sheet for {puzzle['name']}"
        )
        _process_activity_records(records, puzzle, last_sheet_act_ts, threadname, True)
    else:
        # Legacy Revisions API approach
        records = sheet_info.get("revisions", [])
        debug_log(
            4,
            f"[Thread: {threadname}] Processing {len(records)} revision records from Revisions API for {puzzle['name']}"
        )
        _process_activity_records(records, puzzle, last_sheet_act_ts, threadname, False)




# ── Abandoned Puzzle Detection ──────────────────────────────────────────


def _check_abandoned_puzzle(puzzle: Dict[str, Any], threadname: str) -> None:
    """
    Check if puzzle is abandoned and mark it accordingly.

    A puzzle is abandoned if it's "Being worked" with no solvers and no recent activity.

    Args:
        puzzle: Puzzle dictionary from API
        threadname: Name of worker thread (for logging)
    """
    if puzzle.get("status") != "Being worked":
        return

    cur_solvers = puzzle.get("cursolvers")
    if cur_solvers and cur_solvers.strip():
        return  # Has solvers, not abandoned

    # No current solvers, check if activity is stale
    abandoned_timeout_minutes = int(
        configstruct.get("BIGJIMMY_ABANDONED_TIMEOUT_MINUTES", 10)
    )
    abandoned_timeout_seconds = abandoned_timeout_minutes * 60
    abandoned_status = configstruct.get("BIGJIMMY_ABANDONED_STATUS", "Abandoned")

    # Fetch lastact (any activity type - superset of lastsheetact)
    lastact_response = _api_request_with_retry(
        "get", f"{config['API']['APIURI']}/puzzles/{puzzle['id']}/lastact"
    )
    if not lastact_response:
        debug_log(
            2,
            f"[Thread: {threadname}] Failed to fetch lastact for {puzzle['name']} after retries",
        )
        return

    try:
        lastact_data = json.loads(lastact_response.text)
        lastact = lastact_data.get("lastact")
    except Exception as e:
        debug_log(
            2,
            f"[Thread: {threadname}] Error parsing lastact for {puzzle['name']}: {e}",
        )
        return

    if not lastact or not lastact.get("time"):
        # No activity recorded, wait for next cycle
        debug_log(
            4,
            f"[Thread: {threadname}] Puzzle {puzzle['name']} has no activity yet, will check again next cycle",
        )
        return

    try:
        lastact_time = datetime.datetime.strptime(
            lastact["time"], "%a, %d %b %Y %H:%M:%S %Z"
        )
        now = datetime.datetime.utcnow()
        time_since_activity = (now - lastact_time).total_seconds()

        if time_since_activity > abandoned_timeout_seconds:
            debug_log(
                3,
                f"[Thread: {threadname}] Puzzle {puzzle['name']} inactive for {time_since_activity / 60:.1f} min "
                f"(threshold: {abandoned_timeout_minutes}), no solvers",
            )

            response = _api_request_with_retry(
                "post",
                f"{config['API']['APIURI']}/puzzles/{puzzle['id']}/status",
                json={"status": abandoned_status},
            )
            if response:
                debug_log(
                    3,
                    f"[Thread: {threadname}] Set puzzle {puzzle['name']} status to '{abandoned_status}'",
                )
            else:
                debug_log(
                    1,
                    f"[Thread: {threadname}] Failed to update status for {puzzle['name']} after retries",
                )
    except Exception as e:
        debug_log(
            2,
            f"[Thread: {threadname}] Error parsing lastact time for {puzzle['name']}: {e}",
        )


# ── Puzzle Processing ──────────────────────────────────────────────────

def _process_puzzle(puzzle: Dict[str, Any], threadname: str) -> None:
    """
    Process a single puzzle: fetch sheet info, track activity, check abandoned status.

    Args:
        puzzle: Puzzle dictionary from API
        threadname: Name of worker thread (for logging)
    """
    puzzle_start_time = time.time()
    debug_log(4, f"[Thread: {threadname}] Fetched from queue puzzle: {puzzle['name']}")

    # Fetch sheet information (tries to activate add-on if needed)
    sheet_info, sheetenabled = _fetch_sheet_info(puzzle, threadname)

    # Update sheet count if changed
    _update_sheet_count(puzzle, sheet_info, threadname)

    # Process sheet activity and update solver assignments
    _process_sheet_activity(puzzle, sheet_info, sheetenabled, threadname)

    # Check for abandoned puzzles
    _check_abandoned_puzzle(puzzle, threadname)

    # Log per-puzzle timing
    puzzle_elapsed = time.time() - puzzle_start_time
    debug_log(
        4,
        f"[Thread: {threadname}] Finished processing puzzle {puzzle['name']} in {puzzle_elapsed:.2f} seconds",
    )


# ── Worker Thread ──────────────────────────────────────────────────────

def _check_puzzle_from_queue(threadname: str, q: queue.Queue) -> int:
    """
    Worker thread main loop: process puzzles from queue.

    Args:
        threadname: Name of this worker thread (for logging)
        q: Queue containing puzzle dictionaries

    Returns:
        0 on normal exit
    """
    global EXIT_FLAG

    while not EXIT_FLAG:
        QUEUE_LOCK.acquire()
        if not WORK_QUEUE.empty():
            puzzle = q.get()
            QUEUE_LOCK.release()

            # Throttle to avoid API rate limits
            time.sleep(int(configstruct["BIGJIMMY_PUZZLEPAUSETIME"]))

            try:
                _process_puzzle(puzzle, threadname)
            except Exception as e:
                debug_log(
                    1,
                    f"[Thread: {threadname}] Error processing puzzle {puzzle.get('name', 'unknown')}: {e}",
                )
            finally:
                WORK_QUEUE.task_done()
        else:
            QUEUE_LOCK.release()

    debug_log(4, f"Exiting puzzthread {threadname}")
    return 0


class PuzzleThread(threading.Thread):
    """Worker thread for processing puzzles from the queue."""

    def __init__(self, thread_id: int, name: str, q: queue.Queue):
        """
        Initialize puzzle worker thread.

        Args:
            thread_id: Unique thread ID
            name: Thread name (for logging)
            q: Queue to process puzzles from
        """
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.name = name
        self.q = q

    def run(self):
        """Thread main loop."""
        _check_puzzle_from_queue(self.name, self.q)


# ── Metrics & Stats ─────────────────────────────────────────────────────

def _post_botstats_metrics(
    loop_elapsed: float, setup_elapsed: float, processing_elapsed: float, puzzle_count: int
) -> None:
    """
    Post timing statistics to API for Prometheus metrics.

    Args:
        loop_elapsed: Total loop time in seconds
        setup_elapsed: Setup phase time in seconds
        processing_elapsed: Processing phase time in seconds
        puzzle_count: Number of puzzles processed
    """
    _api_request_with_retry(
        "post",
        f"{config['API']['APIURI']}/botstats/loop_time_seconds",
        json={"val": f"{loop_elapsed:.2f}"},
    )
    _api_request_with_retry(
        "post",
        f"{config['API']['APIURI']}/botstats/loop_setup_seconds",
        json={"val": f"{setup_elapsed:.2f}"},
    )
    _api_request_with_retry(
        "post",
        f"{config['API']['APIURI']}/botstats/loop_processing_seconds",
        json={"val": f"{processing_elapsed:.2f}"},
    )
    _api_request_with_retry(
        "post",
        f"{config['API']['APIURI']}/botstats/loop_puzzle_count",
        json={"val": str(puzzle_count)},
    )
    if puzzle_count > 0:
        _api_request_with_retry(
            "post",
            f"{config['API']['APIURI']}/botstats/loop_avg_seconds_per_puzzle",
            json={"val": f"{processing_elapsed / puzzle_count:.2f}"},
        )

    quota_failures = get_quota_failure_count()
    _api_request_with_retry(
        "post",
        f"{config['API']['APIURI']}/botstats/quota_failures",
        json={"val": str(quota_failures)},
    )


# ── Main Bot Loop ───────────────────────────────────────────────────────

def main():
    """Main bot loop: fetch puzzles, spawn workers, wait for completion."""
    global EXIT_FLAG, THREAD_COUNTER, THREADS, LOOP_ITERATIONS_TOTAL

    # Initialize Google Drive API
    if initdrive() != 0:
        debug_log(0, "google drive init failed. Fatal.")
        sys.exit(255)

    debug_log(3, f"google drive init succeeded. Hunt folder id: {pblib.huntfolderid}")

    while True:
        # Reload config from database each loop
        try:
            refresh_config()
            debug_log(5, "Config reloaded from database")
        except Exception as e:
            debug_log(1, f"Error refreshing config: {e}")

        # Increment and post loop iteration counter
        LOOP_ITERATIONS_TOTAL += 1
        response = _api_request_with_retry(
            "post",
            f"{config['API']['APIURI']}/botstats/loop_iterations_total",
            json={"val": str(LOOP_ITERATIONS_TOTAL)},
        )
        if not response:
            debug_log(2, "Failed to post loop iteration counter after retries")

        # Skip if Google API is disabled
        if configstruct.get("SKIP_GOOGLE_API", "false") == "true":
            debug_log(3, "SKIP_GOOGLE_API is true, sleeping 5 seconds")
            time.sleep(5)
            continue

        # Start timing setup phase
        setup_start_time = time.time()

        # Fetch all puzzles
        response = _api_request_with_retry("get", f"{config['API']['APIURI']}/all")
        if not response:
            debug_log(
                1,
                "Error fetching puzzle info from puzzleboss after retries. Puzzleboss down?",
            )
            time.sleep(int(configstruct["BIGJIMMY_PUZZLEPAUSETIME"]))
            continue

        try:
            hunt_data = json.loads(response.text)
        except Exception as e:
            debug_log(1, f"Error parsing JSON from /all endpoint: {e}")
            time.sleep(int(configstruct["BIGJIMMY_PUZZLEPAUSETIME"]))
            continue

        debug_log(5, f"api return: {hunt_data}")
        rounds = hunt_data["rounds"]
        debug_log(4, "loaded round list")

        # Build list of unsolved puzzles
        puzzles = []
        for rnd in rounds:
            puzzles_in_round = rnd["puzzles"]
            debug_log(
                4, f"appending puzzles from round {rnd['id']}: {puzzles_in_round}"
            )
            for puzzle in puzzles_in_round:
                if puzzle["status"] != "Solved":
                    puzzles.append(puzzle)
                else:
                    debug_log(4, f"skipping solved puzzle {puzzle['name']}")
        debug_log(4, "full puzzle structure loaded")

        # Spawn worker threads
        thread_count = int(configstruct["BIGJIMMY_THREADCOUNT"])
        for i in range(1, thread_count + 1):
            thread = PuzzleThread(THREAD_COUNTER, i, WORK_QUEUE)
            thread.start()
            THREADS.append(thread)
            THREAD_COUNTER += 1

        # Put all puzzles in the queue
        QUEUE_LOCK.acquire()
        for puzzle in puzzles:
            WORK_QUEUE.put(puzzle)
        QUEUE_LOCK.release()

        # Setup complete, start timing processing phase
        setup_elapsed = time.time() - setup_start_time
        processing_start_time = time.time()
        debug_log(
            4,
            f"Beginning iteration of bigjimmy bot across all puzzles (setup took {setup_elapsed:.2f} sec)",
        )

        # Wait for all tasks to complete
        WORK_QUEUE.join()

        # Signal threads to exit and wait for them
        EXIT_FLAG = 1
        for t in THREADS:
            t.join()

        processing_elapsed = time.time() - processing_start_time
        loop_elapsed = setup_elapsed + processing_elapsed
        debug_log(4, "Completed iteration of bigjimmy bot across all puzzles")
        debug_log(
            3,
            f"Full iteration completed: {len(puzzles)} puzzles in {loop_elapsed:.2f} sec "
            f"(setup: {setup_elapsed:.2f} sec, processing: {processing_elapsed:.2f} sec, "
            f"{processing_elapsed / len(puzzles) if puzzles else 0:.2f} sec/puzzle avg)",
        )

        # Post timing stats to API for Prometheus metrics
        _post_botstats_metrics(loop_elapsed, setup_elapsed, processing_elapsed, len(puzzles))

        # Reset for next iteration
        EXIT_FLAG = 0
        THREADS = []


if __name__ == "__main__":
    main()
