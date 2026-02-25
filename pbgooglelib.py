"""Google Drive/Sheets integration — sheet creation, activity tracking, and user management."""

import os.path
import sys
import time
import random
import threading
from typing import Optional
import googleapiclient
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2 import service_account
import google_auth_httplib2
import httplib2
import pblib
import datetime
import json
from pblib import debug_log, configstruct


service = None
sheetsservice = None
creds = None
admincreds = None

# Thread-local storage for reusable AuthorizedHttp clients.
# Each bigjimmy worker thread gets ONE http client that's reused across
# all Google API calls in that thread, instead of creating a new one per call.
_thread_local = threading.local()


def _get_thread_http():
    """Return a reusable AuthorizedHttp for the current thread.

    Creates one on first call per thread; reuses it thereafter.
    This avoids the memory leak of creating a new httplib2.Http() +
    AuthorizedHttp wrapper on every API call (60-80 per iteration).
    """
    http = getattr(_thread_local, "authorized_http", None)
    if http is None and creds is not None:
        http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http())
        _thread_local.authorized_http = http
    return http


# Cached Apps Script API service client (created on first use).
# build() downloads and parses the discovery document (~50-100 KB),
# so we only want to do it once.
_script_service = None
_script_service_lock = threading.Lock()

# Thread-safe counter for quota failures (read by bigjimmybot for metrics)
quota_failure_count = 0
quota_failure_lock = threading.Lock()

# Default retry/delay constants (can be overridden via config)
_DEFAULT_MAX_RETRIES = 10
_DEFAULT_RETRY_DELAY_SECONDS = 5

# Default queries-per-minute limit (Google Sheets API hard limit is 60)
_DEFAULT_QPM = 55


class _GoogleApiRateLimiter:
    """Global rate limiter for Google API calls using slot reservation.

    Ensures API calls are spaced at minimum intervals to stay within
    the Google Sheets API's per-minute quota. Thread-safe.

    Threads call acquire() before making any Google API request.
    Each call reserves the next available time slot and sleeps until
    that slot arrives. QPM is read from config on each call so it
    can be tuned at runtime via the admin UI.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def acquire(self):
        """Block until the next API call slot is available."""
        qpm = int(configstruct.get("BIGJIMMY_GOOGLE_API_QPM", _DEFAULT_QPM))
        min_interval = 60.0 / max(qpm, 1)

        with self._lock:
            now = time.time()
            if self._next_slot <= now:
                # Slot is in the past — go immediately, reserve next
                self._next_slot = now + min_interval
                wait_time = 0.0
            else:
                # Must wait for the next slot
                wait_time = self._next_slot - now
                self._next_slot += min_interval

        if wait_time > 0:
            time.sleep(wait_time)


_rate_limiter = _GoogleApiRateLimiter()


def _increment_quota_failure():
    """Thread-safe increment of quota failure counter."""
    global quota_failure_count
    with quota_failure_lock:
        quota_failure_count += 1


def get_quota_failure_count():
    """Get current quota failure count (called by bigjimmybot)."""
    with quota_failure_lock:
        return quota_failure_count


SCOPES = [
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.appdata",
    "https://www.googleapis.com/auth/drive.file",
]

ADMINSCOPES = ["https://www.googleapis.com/auth/admin.directory.user"]


def _get_service_account_file():
    """Get the path to the service account JSON key file."""
    # Check config table first, then fall back to default path
    sa_file = configstruct.get("SERVICE_ACCOUNT_FILE", "service-account.json")
    if not os.path.exists(sa_file):
        debug_log(0, f"Service account file not found: {sa_file}")
        raise Exception(
            f"Service account key file '{sa_file}' not found. "
            "Download it from Google Cloud Console and place it in the app directory."
        )
    return sa_file


def _get_impersonation_subject():
    """Get the domain user email to impersonate for API calls."""
    subject = configstruct.get("SERVICE_ACCOUNT_SUBJECT", "")
    if not subject:
        debug_log(0, "SERVICE_ACCOUNT_SUBJECT not set in config table")
        raise Exception(
            "SERVICE_ACCOUNT_SUBJECT must be set in the config table to a domain admin email "
            "(e.g. bigjimmy@importanthuntpoll.org) for service account impersonation."
        )
    return subject


def initadmin():
    """Initialize admin credentials via service account with Domain-Wide Delegation."""
    debug_log(4, "start")

    global admincreds
    global ADMINSCOPES

    if admincreds is not None:
        debug_log(5, "Admin credentials already initialized, skipping")
        return

    sa_file = _get_service_account_file()
    subject = _get_impersonation_subject()

    debug_log(4, f"Loading admin credentials from service account: {sa_file} (subject: {subject})")
    admincreds = service_account.Credentials.from_service_account_file(
        sa_file, scopes=ADMINSCOPES, subject=subject
    )
    debug_log(3, "Admin credentials initialized via service account")


def initdrive():
    """Initialize Drive and Sheets services; create hunt folder if needed. Returns 0.

    Safe to call multiple times — skips if already initialized.
    Previously re-created credentials and service clients on every call,
    leaking ~100 KB of parsed discovery documents each time.
    """
    debug_log(4, "start")

    if configstruct["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google docs auth and init skipped by config.")
        return 0

    global service
    global sheetsservice
    global creds
    global SCOPES

    # Skip if already initialized — avoids recreating credentials and
    # build() service clients on every Google API operation.
    if service is not None and sheetsservice is not None and creds is not None:
        debug_log(5, "Drive/Sheets services already initialized, skipping")
        return 0

    sa_file = _get_service_account_file()
    subject = _get_impersonation_subject()

    debug_log(4, f"Loading Drive/Sheets credentials from service account: {sa_file} (subject: {subject})")
    creds = service_account.Credentials.from_service_account_file(
        sa_file, scopes=SCOPES, subject=subject
    )

    service = build("drive", "v3", credentials=creds)
    sheetsservice = build("sheets", "v4", credentials=creds)
    debug_log(3, "Drive and Sheets services initialized via service account")

    foldername = configstruct["HUNT_FOLDER_NAME"]

    # Check if hunt folder exists
    _rate_limiter.acquire()
    huntfoldercheck = (
        service.files()
        .list(
            fields="files(name), files(id)", spaces="drive", q=f"name='{foldername}'"
        )
        .execute()
    )
    matchingfolders = huntfoldercheck.get("files", None)
    debug_log(5, f"folder search result= {matchingfolders}")

    # Create initial hunt folder if it doesn't exist
    if not matchingfolders or matchingfolders == []:
        debug_log(3, f"Folder named {foldername} not found. Creating.")

        file_metadata = {
            "name": foldername,
            "mimeType": "application/vnd.google-apps.folder",
        }
        _rate_limiter.acquire()
        folder_file = service.files().create(body=file_metadata, fields="id").execute()

        # Set global variable
        pblib.huntfolderid = folder_file.get("id")
        debug_log(
            3,
            f"New hunt root folder {foldername} created with id {pblib.huntfolderid}",
        )
    elif len(matchingfolders) > 1:
        errmsg = f"Multiple folders found matching name {foldername}! Fix this."
        debug_log(0, errmsg)
        sys.exit(255)
    else:
        debug_log(
            4,
            f"Folder named {foldername} found to already exist with id {matchingfolders[0]['id']}",
        )
        pblib.huntfolderid = matchingfolders[0]["id"]
    return 0


def get_puzzle_sheet_info_activity(myfileid, puzzlename=None):
    """
    Get editor activity from the hidden '_pb_activity' sheet.
    Returns dict with 'editors' (list of {solvername, timestamp}) and 'sheetcount' (int or None).

    This is the Apps Script API approach: a simple onEdit trigger writes editor
    email, unix timestamp, and sheet count to a pre-created hidden sheet named
    '_pb_activity'. This function reads that data via the Sheets values API.

    Email-to-username conversion: strips the @domain portion from the email
    address to produce the puzzleboss username (e.g. 'alice@example.org' → 'alice').

    THREAD SAFE.
    Includes retry logic for rate limit (429) errors.

    Args:
        myfileid: Google Sheets file ID
        puzzlename: Optional puzzle name for logging
    """
    puzz_label = puzzlename if puzzlename else myfileid
    debug_log(5, f"start _pb_activity read for puzzle {puzz_label} (fileid: {myfileid})")

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", _DEFAULT_MAX_RETRIES))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", _DEFAULT_RETRY_DELAY_SECONDS))

    result = {"editors": [], "sheetcount": None, "error": False}

    if configstruct["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google API skipped by config.")
        return result

    threadsafe_http = _get_thread_http()

    for attempt in range(max_retries):
        try:
            _rate_limiter.acquire()
            response = (
                sheetsservice.spreadsheets()
                .values()
                .get(
                    spreadsheetId=myfileid,
                    range="_pb_activity!A:C",
                )
                .execute(http=threadsafe_http)
            )

            rows = response.get("values", [])
            debug_log(
                4,
                f"[{puzz_label}] _pb_activity returned {len(rows)} rows (including header)",
            )

            # Skip header row (editor, timestamp, num_sheets)
            for row in rows[1:]:
                if len(row) < 2:
                    continue

                email = str(row[0]).strip()
                try:
                    timestamp = int(row[1])
                except (ValueError, TypeError):
                    debug_log(
                        2,
                        f"[{puzz_label}] Invalid timestamp in _pb_activity row: {row}",
                    )
                    continue

                # Convert email to puzzleboss username (strip @domain)
                solvername = email.split("@")[0] if "@" in email else email

                result["editors"].append({
                    "solvername": solvername,
                    "timestamp": timestamp,
                })

                # Use the most recent num_sheets value as the sheet count
                if len(row) >= 3:
                    try:
                        result["sheetcount"] = int(row[2])
                    except (ValueError, TypeError):
                        pass

                debug_log(
                    4,
                    f"[{puzz_label}] Parsed editor activity: solver={solvername} timestamp={timestamp}",
                )

            debug_log(
                5,
                f"[{puzz_label}] Found {len(result['editors'])} editors with activity, sheetcount={result['sheetcount']}",
            )
            break  # Success, exit retry loop

        except googleapiclient.errors.HttpError as e:
            if e.resp.status == 400 and "Unable to parse range" in str(e):
                # _pb_activity sheet doesn't exist yet (no one has edited)
                debug_log(
                    4,
                    f"[{puzz_label}] _pb_activity sheet not found (no edits yet)",
                )
                break
            elif e.resp.status == 429 or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(
                    3,
                    f"[{puzz_label}] Rate limit hit reading _pb_activity, waiting {retry_delay} seconds (attempt {attempt + 1}/{max_retries})",
                )
                time.sleep(retry_delay * random.uniform(0.5, 1.5))
            else:
                debug_log(1, f"[{puzz_label}] Error reading _pb_activity: {e}")
                result["error"] = True
                break
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(
                    3,
                    f"[{puzz_label}] Rate limit hit reading _pb_activity, waiting {retry_delay} seconds (attempt {attempt + 1}/{max_retries})",
                )
                time.sleep(retry_delay * random.uniform(0.5, 1.5))
            else:
                debug_log(1, f"[{puzz_label}] Error reading _pb_activity: {e}")
                result["error"] = True
                break  # Non-rate-limit error, don't retry
    else:
        if max_retries > 0:
            debug_log(
                1,
                f"[{puzz_label}] EXHAUSTED all {max_retries} retries reading _pb_activity - giving up",
            )
            result["error"] = True

    return result


def get_puzzle_sheet_info_legacy(myfileid, puzzlename=None):
    """
    Get revisions and sheet count using the old API approach (Revisions API + Sheets API).
    Returns dict with 'revisions' (list) and 'sheetcount' (int or None).

    This is the fallback method for sheets that don't have the Chrome extension enabled.

    THREAD SAFE.
    Includes retry logic for rate limit (429) errors.

    Args:
        myfileid: Google Sheets file ID
        puzzlename: Optional puzzle name for logging
    """
    puzz_label = puzzlename if puzzlename else myfileid
    debug_log(5, f"start (legacy) for puzzle {puzz_label} (fileid: {myfileid})")

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", _DEFAULT_MAX_RETRIES))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", _DEFAULT_RETRY_DELAY_SECONDS))

    result = {"revisions": [], "sheetcount": None, "error": False}

    if configstruct["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google API skipped by config.")
        return result

    threadsafe_http = _get_thread_http()

    # Get revisions from Drive API (with retry on rate limit)
    # Only fetch the fields the caller actually uses (emailAddress, me, modifiedTime).
    # fields="*" previously fetched ~20 fields per revision including exportLinks,
    # md5Checksum, size, etc. — wasting ~400-800 bytes/revision × hundreds of revisions.
    revisions_fields = "revisions(lastModifyingUser(emailAddress,me),modifiedTime)"
    revisions_success = False
    for attempt in range(max_retries):
        try:
            _rate_limiter.acquire()
            retval = (
                service.revisions()
                .list(fileId=myfileid, fields=revisions_fields)
                .execute(http=threadsafe_http)
            )
            if isinstance(retval, str):
                debug_log(
                    1,
                    f"[{puzz_label}] Revisions API returned string (error): {retval}",
                )
            else:
                all_revisions = retval.get("revisions", [])
                debug_log(
                    5,
                    f"[{puzz_label}] Revisions API returned {len(all_revisions)} total revisions",
                )
                for revision in all_revisions:
                    last_user = revision.get("lastModifyingUser", {})
                    is_me = last_user.get("me", False)
                    if not is_me:
                        result["revisions"].append(revision)
                debug_log(
                    5,
                    f"[{puzz_label}] After filtering, {len(result['revisions'])} revisions",
                )
            revisions_success = True
            break  # Success, exit retry loop
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(
                    3,
                    f"[{puzz_label}] Rate limit hit fetching revisions, waiting {retry_delay} seconds (attempt {attempt + 1}/{max_retries})",
                )
                time.sleep(retry_delay * random.uniform(0.5, 1.5))
            else:
                debug_log(1, f"[{puzz_label}] Error fetching revisions: {e}")
                result["error"] = True
                break  # Non-rate-limit error, don't retry

    if not revisions_success and max_retries > 0:
        debug_log(
            1,
            f"[{puzz_label}] EXHAUSTED all {max_retries} retries fetching revisions - giving up",
        )
        result["error"] = True

    # Get sheet count from Sheets API (with retry on rate limit)
    sheetcount_success = False
    for attempt in range(max_retries):
        try:
            _rate_limiter.acquire()
            spreadsheet = (
                sheetsservice.spreadsheets()
                .get(spreadsheetId=myfileid, fields="sheets.properties.title")
                .execute(http=threadsafe_http)
            )
            result["sheetcount"] = len(spreadsheet.get("sheets", []))
            debug_log(5, f"[{puzz_label}] Sheet count: {result['sheetcount']}")
            sheetcount_success = True
            break  # Success, exit retry loop
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(
                    3,
                    f"[{puzz_label}] Rate limit hit getting sheet count, waiting {retry_delay} seconds (attempt {attempt + 1}/{max_retries})",
                )
                time.sleep(retry_delay * random.uniform(0.5, 1.5))
            else:
                debug_log(1, f"[{puzz_label}] Error getting sheet count: {e}")
                result["error"] = True
                break  # Non-rate-limit error, don't retry

    if not sheetcount_success and max_retries > 0:
        debug_log(
            1,
            f"[{puzz_label}] EXHAUSTED all {max_retries} retries getting sheet count - giving up",
        )
        result["error"] = True

    return result


def repair_activity_sheet(sheet_id: str, puzzlename: Optional[str] = None) -> bool:
    """
    Repair a corrupt _pb_activity sheet by deleting and recreating it.

    Steps:
      1. Get spreadsheet metadata to find the _pb_activity tab's sheetId
      2. Delete the tab via batchUpdate deleteSheet request
      3. Recreate the tab (hidden + protected + headers)

    Returns True on success, False on failure. Non-fatal.
    Uses the main sheets credentials (no script.projects scope needed).

    Args:
        sheet_id: Google Sheets file ID (drive_id)
        puzzlename: Optional puzzle name for logging
    """
    puzz_label = puzzlename if puzzlename else sheet_id
    debug_log(2, f"[{puzz_label}] repair_activity_sheet start (sheet_id: {sheet_id})")

    if configstruct.get("SKIP_GOOGLE_API") == "true":
        debug_log(3, f"[{puzz_label}] Skipping repair (SKIP_GOOGLE_API)")
        return False

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", _DEFAULT_MAX_RETRIES))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", _DEFAULT_RETRY_DELAY_SECONDS))

    threadsafe_http = _get_thread_http()

    # ── Step 1: Find the _pb_activity tab's sheetId ───────────────
    activity_tab_id = None
    for attempt in range(max_retries):
        try:
            _rate_limiter.acquire()
            spreadsheet = sheetsservice.spreadsheets().get(
                spreadsheetId=sheet_id,
                fields="sheets.properties",
            ).execute(http=threadsafe_http)

            for sheet in spreadsheet.get("sheets", []):
                props = sheet.get("properties", {})
                if props.get("title") == _ACTIVITY_SHEET_NAME:
                    activity_tab_id = props["sheetId"]
                    break
            break  # Success (even if tab not found)
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(3, f"[{puzz_label}] Rate limit getting metadata, waiting {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay * random.uniform(0.5, 1.5))
            else:
                debug_log(1, f"[{puzz_label}] Failed to get spreadsheet metadata: {e}")
                return False
    else:
        debug_log(1, f"[{puzz_label}] EXHAUSTED retries getting spreadsheet metadata")
        return False

    # ── Step 2: Delete the existing tab (if found) ────────────────
    if activity_tab_id is not None:
        for attempt in range(max_retries):
            try:
                _rate_limiter.acquire()
                sheetsservice.spreadsheets().batchUpdate(
                    spreadsheetId=sheet_id,
                    body={"requests": [{
                        "deleteSheet": {"sheetId": activity_tab_id}
                    }]},
                ).execute(http=threadsafe_http)
                debug_log(2, f"[{puzz_label}] Deleted corrupt _pb_activity tab (sheetId={activity_tab_id})")
                break
            except Exception as e:
                if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                    _increment_quota_failure()
                    debug_log(3, f"[{puzz_label}] Rate limit deleting tab, waiting {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay * random.uniform(0.5, 1.5))
                else:
                    debug_log(1, f"[{puzz_label}] Failed to delete _pb_activity tab: {e}")
                    return False
        else:
            debug_log(1, f"[{puzz_label}] EXHAUSTED retries deleting _pb_activity tab")
            return False
    else:
        debug_log(3, f"[{puzz_label}] _pb_activity tab not found — will create fresh")

    # ── Step 3: Recreate the tab (hidden + protected + headers) ───
    try:
        _rate_limiter.acquire()
        add_result = sheetsservice.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{
                "addSheet": {
                    "properties": {
                        "title": _ACTIVITY_SHEET_NAME,
                        "hidden": True,
                    }
                }
            }]},
        ).execute(http=threadsafe_http)

        new_sheet_id = add_result["replies"][0]["addSheet"]["properties"]["sheetId"]

        # Write headers
        _rate_limiter.acquire()
        sheetsservice.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{_ACTIVITY_SHEET_NAME}!A1:C1",
            valueInputOption="RAW",
            body={"values": [["editor", "timestamp", "num_sheets"]]},
        ).execute(http=threadsafe_http)

        # Add warning-only protection
        _rate_limiter.acquire()
        sheetsservice.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{
                "addProtectedRange": {
                    "protectedRange": {
                        "range": {"sheetId": new_sheet_id},
                        "description": "Managed by Puzzleboss — do not edit manually.",
                        "warningOnly": True,
                    }
                }
            }]},
        ).execute(http=threadsafe_http)

        debug_log(2, f"[{puzz_label}] Recreated _pb_activity sheet successfully")
        return True

    except Exception as e:
        debug_log(1, f"[{puzz_label}] Failed to recreate _pb_activity sheet: {e}")
        return False


def create_round_folder(foldername):
    """Create a Google Drive folder for a round. Returns the folder ID."""
    debug_log(4, f"start with foldername: {foldername}")

    if configstruct["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google round folder creation skipped by config.")
        return "xxxskippedbyconfigxxx"

    initdrive()

    file_metadata = {
        "name": foldername,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [pblib.huntfolderid],
    }

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", _DEFAULT_MAX_RETRIES))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", _DEFAULT_RETRY_DELAY_SECONDS))

    folder_file = None
    for attempt in range(max_retries):
        try:
            _rate_limiter.acquire()
            folder_file = service.files().create(body=file_metadata, fields="id").execute()
            debug_log(4, f"folder id returned: {folder_file.get('id')}")
            break  # Success
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                debug_log(
                    3,
                    f"Rate limit hit creating round folder, waiting {retry_delay} seconds (attempt {attempt + 1}/{max_retries})",
                )
                time.sleep(retry_delay * random.uniform(0.5, 1.5))
            else:
                debug_log(0, f"Error creating round folder: {e}")
                sys.exit(255)

    if folder_file is None:
        debug_log(
            0,
            f"EXHAUSTED all {max_retries} retries creating round folder - giving up",
        )
        sys.exit(255)

    return folder_file.get("id")


def delete_puzzle_sheet(sheetid):
    """Trash a puzzle sheet in Google Drive. Returns 0 on success, 255 on error."""
    debug_log(4, f"start delete with sheet id: {sheetid}")

    initdrive()

    body_value = {"trashed": True}

    try:
        _rate_limiter.acquire()
        service.files().update(fileId=sheetid, body=body_value).execute()

    except Exception as e:
        debug_log(1, f"Delete failed for sheet {sheetid}. Error is {e}.")
        return 255

    return 0


def create_puzzle_sheet(parentfolder, puzzledict):
    """Create a Google Sheet for a puzzle with metadata, work sheets, and permissions. Returns sheet ID."""
    debug_log(
        4, f"start with parentfolder: {parentfolder}, puzzledict {puzzledict}"
    )
    name = puzzledict["name"]

    if configstruct["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google puzzle creation skipped by config.")
        return "xxxskippedbyconfigxxx"

    initdrive()

    file_metadata = {
        "name": name,
        "parents": [parentfolder],
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", _DEFAULT_MAX_RETRIES))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", _DEFAULT_RETRY_DELAY_SECONDS))

    # Create/copy file with retry logic
    sheet_file = None
    for attempt in range(max_retries):
        try:
            _rate_limiter.acquire()
            if configstruct["SHEETS_TEMPLATE_ID"] == "none":
                sheet_file = service.files().create(body=file_metadata, fields="id").execute()
                debug_log(4, f"file ID returned from creation: {sheet_file.get('id')}")
            else:
                sheet_file = (
                    service.files()
                    .copy(
                        body=file_metadata,
                        fileId=configstruct["SHEETS_TEMPLATE_ID"],
                        fields="id",
                    )
                    .execute()
                )
                debug_log(4, f"file ID returned from copy: {sheet_file.get('id')}")
            break  # Success
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                debug_log(
                    3,
                    f"Rate limit hit creating file, waiting {retry_delay} seconds (attempt {attempt + 1}/{max_retries})",
                )
                time.sleep(retry_delay * random.uniform(0.5, 1.5))
            else:
                debug_log(0, f"Error creating puzzle sheet file: {e}")
                sys.exit(255)

    if sheet_file is None:
        debug_log(
            0,
            f"EXHAUSTED all {max_retries} retries creating puzzle sheet - giving up",
        )
        sys.exit(255)

    # Now let's set initial contents
    requests = []

    sheet_properties = {
        "metadata": {
            "sheetId": 1,
            "title": "Metadata",
            "gridProperties": {
                "rowCount": 7,
                "columnCount": 2,
                "hideGridlines": True,
            },
            "index": 0,
        },
        "work": {
            "sheetId": 0,
            "title": "Work",
            "gridProperties": {
                "rowCount": 100,
                "columnCount": 26,
                "frozenRowCount": 1,
            },
            "index": 2,
        },
    }

    def get_fields(properties, prefix=""):
        fields = []
        for key in properties.keys():
            if not prefix and key == "sheetId":
                continue
            label = prefix + "." + key if prefix else key
            if isinstance(properties[key], dict):
                fields.append(get_fields(properties[key], prefix=label))
            else:
                fields.append(label)
        return ",".join(fields)

    # Create new page if we're not doing a template copy
    if configstruct["SHEETS_TEMPLATE_ID"] == "none":
        requests.append(
            {
                "addSheet": {
                    "properties": sheet_properties["metadata"],
                }
            }
        )

        requests.append(
            {
                "addSheet": {
                    "properties": sheet_properties["work"],
                }
            }
        )
    else:
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": sheet_properties["metadata"],
                    "fields": get_fields(sheet_properties["metadata"]),
                }
            }
        )

        # Relabel existing sheet as "Work" and setup appropriately
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": sheet_properties["work"],
                    "fields": get_fields(sheet_properties["work"]),
                }
            }
        )

    # Set format of metadata sheet
    requests.append(
        {
            "updateDimensionProperties": {
                "properties": {"pixelSize": 150},
                "range": {
                    "sheetId": 1,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": 1,
                },
                "fields": "pixelSize",
            }
        }
    )
    requests.append(
        {
            "updateDimensionProperties": {
                "properties": {"pixelSize": 1000},
                "range": {
                    "sheetId": 1,
                    "dimension": "COLUMNS",
                    "startIndex": 1,
                    "endIndex": 2,
                },
                "fields": "pixelSize",
            }
        }
    )

    def hyperlink(url, label=None):
        return f'=HYPERLINK("{url}", "{label or url}")'

    # Set content of metadata sheet
    requests.append(
        {
            "updateCells": {
                "range": {
                    "sheetId": 1,
                    "startRowIndex": 0,
                    "startColumnIndex": 0,
                    "endRowIndex": 7,
                    "endColumnIndex": 2,
                },
                "fields": "userEnteredValue, effectiveValue, textFormatRuns",
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": "Round Name:"},
                                "userEnteredFormat": {"textFormat": {"bold": True}},
                            },
                            {
                                "userEnteredValue": {
                                    "stringValue": puzzledict["roundname"]
                                }
                            },
                        ]
                    },
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": "Puzzle Name:"},
                                "userEnteredFormat": {"textFormat": {"bold": True}},
                            },
                            {"userEnteredValue": {"stringValue": puzzledict["name"]}},
                        ]
                    },
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": "Puzzle URL:"},
                                "userEnteredFormat": {"textFormat": {"bold": True}},
                            },
                            {
                                "userEnteredValue": {
                                    "formulaValue": hyperlink(puzzledict["puzzle_uri"])
                                }
                            },
                        ]
                    },
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": "Discord Channel:"},
                                "userEnteredFormat": {"textFormat": {"bold": True}},
                            },
                            {
                                "userEnteredValue": {
                                    "formulaValue": hyperlink(
                                        puzzledict["chat_uri"],
                                        label="#" + puzzledict["name"],
                                    )
                                },
                                "userEnteredFormat": {
                                    "textFormat": {
                                        "fontFamily": "Roboto Mono",
                                    },
                                },
                            },
                        ]
                    },
                    {
                        "values": [
                            {
                                "userEnteredValue": {
                                    "stringValue": "NO SPOILERS HERE PLEASE"
                                }
                            }
                        ]
                    },
                    {
                        "values": [
                            {
                                "userEnteredValue": {
                                    "stringValue": "Use the work sheet (see tabs below) for work and create additional sheets as needed."
                                }
                            }
                        ]
                    },
                    {"values": [_color_palette_cell_value()]},
                ],
            }
        }
    )

    body = {"requests": requests}

    debug_log(
        4, f"Sheets api batchupdate request id: {sheet_file.get('id')} body {body}"
    )

    # Batch update with retry logic
    response = None
    for attempt in range(max_retries):
        try:
            _rate_limiter.acquire()
            response = (
                sheetsservice.spreadsheets()
                .batchUpdate(spreadsheetId=sheet_file.get("id"), body=body)
                .execute()
            )
            debug_log(
                5, f"Response from sheetservice.spreadsheets.batchUpdate: {response}"
            )
            break  # Success
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                debug_log(
                    3,
                    f"Rate limit hit on batchUpdate, waiting {retry_delay} seconds (attempt {attempt + 1}/{max_retries})",
                )
                time.sleep(retry_delay * random.uniform(0.5, 1.5))
            else:
                debug_log(0, f"Error in batchUpdate for puzzle sheet: {e}")
                sys.exit(255)

    if response is None:
        debug_log(
            0, f"EXHAUSTED all {max_retries} retries on batchUpdate - giving up"
        )
        sys.exit(255)

    permission = {
        "role": "writer",
        "type": "domain",
        "domain": configstruct["DOMAINNAME"],
    }

    # Set permissions with retry logic
    permresp = None
    for attempt in range(max_retries):
        try:
            _rate_limiter.acquire()
            permresp = (
                service.permissions()
                .create(fileId=sheet_file.get("id"), body=permission)
                .execute()
            )
            debug_log(5, f"Response from service.permissions.create: {permresp}")
            break  # Success
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                debug_log(
                    3,
                    f"Rate limit hit setting permissions, waiting {retry_delay} seconds (attempt {attempt + 1}/{max_retries})",
                )
                time.sleep(retry_delay * random.uniform(0.5, 1.5))
            else:
                debug_log(0, f"Error setting permissions for puzzle sheet: {e}")
                sys.exit(255)

    if permresp is None:
        debug_log(
            0, f"EXHAUSTED all {max_retries} retries setting permissions - giving up"
        )
        sys.exit(255)

    return sheet_file.get("id")


# ── Apps Script code pushed to container-bound script projects ──────
# This is the simple onEdit trigger that writes editor activity to a
# hidden '_pb_activity' sheet. It's pushed to each puzzle sheet when
# activate_puzzle_sheet_via_api() is called with no custom code configured.
#
# Why use a hidden sheet for tracking?
# Simple triggers can write to sheets without requiring user authorization.
# The hidden sheet approach allows activity tracking to work immediately
# without any user authorization prompts.
_APPS_SCRIPT_ONEDIT_CODE = r"""
/**
 * PB Activity Tracker — simple onEdit trigger.
 * Writes editor activity to a '_pb_activity' sheet.
 * No authorization required (runs as simple trigger).
 *
 * The _pb_activity sheet is pre-created, hidden, and warning-protected
 * by the Puzzleboss service account. If somehow missing, the trigger
 * will create it (but it won't be hidden in that case).
 */

var ACTIVITY_SHEET_NAME = '_pb_activity';

/**
 * Simple trigger — fires on every manual edit.
 * Records the editor's email and Unix timestamp.
 * One row per editor, updated in place on subsequent edits.
 */
function onEdit(e) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var actSheet = ss.getSheetByName(ACTIVITY_SHEET_NAME);

    // Fallback: create the sheet if it doesn't exist (shouldn't happen
    // in normal flow — the service account pre-creates it)
    if (!actSheet) {
      actSheet = ss.insertSheet(ACTIVITY_SHEET_NAME);
      actSheet.getRange('A1').setValue('editor');
      actSheet.getRange('B1').setValue('timestamp');
      actSheet.getRange('C1').setValue('num_sheets');
    }

    // Get editor info — simple triggers can access e.user in Sheets
    var editor = '';
    if (e && e.user) {
      editor = e.user.getEmail();
    }
    if (!editor) {
      try {
        editor = Session.getActiveUser().getEmail();
      } catch(ex) {
        editor = 'unknown';
      }
    }

    var now = Math.floor(Date.now() / 1000);
    // Count sheets, excluding the activity sheet itself
    var numSheets = ss.getSheets().length - 1;

    // Update or insert editor row (use toString for safe comparison)
    var data = actSheet.getDataRange().getValues();
    var found = false;
    for (var i = 1; i < data.length; i++) {
      if (String(data[i][0]).trim() === String(editor).trim()) {
        actSheet.getRange(i + 1, 2).setValue(now);
        actSheet.getRange(i + 1, 3).setValue(numSheets);
        found = true;
        break;
      }
    }
    if (!found) {
      var lastRow = actSheet.getLastRow() + 1;
      actSheet.getRange(lastRow, 1).setValue(editor);
      actSheet.getRange(lastRow, 2).setValue(now);
      actSheet.getRange(lastRow, 3).setValue(numSheets);
    }
  } catch(err) {
    // Simple triggers can't easily log errors — silently fail
  }
}
"""

_APPS_SCRIPT_MANIFEST = json.dumps({
    "timeZone": "America/New_York",
    "exceptionLogging": "STACKDRIVER",
    "runtimeVersion": "V8",
})

_ACTIVITY_SHEET_NAME = "_pb_activity"


def activate_puzzle_sheet_via_api(sheet_id: str, puzzlename: Optional[str] = None) -> bool:
    """
    Activate puzzle tools/tracking via the official Apps Script API.

    Creates a container-bound Apps Script project on the spreadsheet and
    pushes configurable Apps Script code. The code can be customized via
    config values:
      - GOOGLE_APPS_SCRIPT_CODE: The Apps Script code to deploy (falls back to
        default onEdit activity tracker if not set)
      - GOOGLE_APPS_SCRIPT_MANIFEST: The appsscript.json manifest (falls back
        to default if not set)

    Uses the existing service account with Domain-Wide Delegation.
    Requires the 'https://www.googleapis.com/auth/script.projects'
    scope in the DWD config and the Apps Script API enabled in
    Google Cloud Console.

    Returns True on success, False on failure. Failures are non-fatal;
    bigjimmybot will fall back to the legacy Revisions API for tracking.

    Args:
        sheet_id: Google Sheets file ID (drive_id)
        puzzlename: Optional puzzle name for logging
    """
    puzz_label = puzzlename if puzzlename else sheet_id
    debug_log(4, f"[{puzz_label}] activate_puzzle_sheet_via_api start (sheet_id: {sheet_id})")

    if configstruct.get("SKIP_GOOGLE_API") == "true":
        debug_log(3, f"[{puzz_label}] Skipping API activation (SKIP_GOOGLE_API)")
        return False

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", _DEFAULT_MAX_RETRIES))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", _DEFAULT_RETRY_DELAY_SECONDS))

    # Get the Apps Script code to deploy (configurable or default)
    addon_code = configstruct.get("GOOGLE_APPS_SCRIPT_CODE", "").strip()
    addon_manifest = configstruct.get("GOOGLE_APPS_SCRIPT_MANIFEST", "").strip()

    if not addon_code:
        addon_code = _APPS_SCRIPT_ONEDIT_CODE
        debug_log(4, f"[{puzz_label}] Using default onEdit activity tracker")
    else:
        debug_log(3, f"[{puzz_label}] Using custom Apps Script code from config (GOOGLE_APPS_SCRIPT_CODE)")

    if not addon_manifest:
        addon_manifest = _APPS_SCRIPT_MANIFEST
    else:
        # Validate manifest is parseable JSON
        try:
            json.loads(addon_manifest)
        except json.JSONDecodeError as e:
            debug_log(1, f"[{puzz_label}] GOOGLE_APPS_SCRIPT_MANIFEST is invalid JSON ({e}), using default")
            addon_manifest = _APPS_SCRIPT_MANIFEST

    # Get or create cached script service client (needs script.projects scope)
    global _script_service
    with _script_service_lock:
        if _script_service is None:
            sa_file = _get_service_account_file()
            subject = _get_impersonation_subject()
            if not sa_file or not subject:
                debug_log(1, f"[{puzz_label}] Cannot activate via API — service account not configured")
                return False
            try:
                api_creds = service_account.Credentials.from_service_account_file(
                    sa_file,
                    scopes=[
                        "https://www.googleapis.com/auth/drive",
                        "https://www.googleapis.com/auth/spreadsheets",
                        "https://www.googleapis.com/auth/script.projects",
                    ],
                    subject=subject,
                )
                api_creds.refresh(Request())
                _script_service = build("script", "v1", credentials=api_creds)
                debug_log(3, f"[{puzz_label}] Created and cached Apps Script service client")
            except Exception as e:
                debug_log(1, f"[{puzz_label}] Failed to create API credentials: {e}")
                return False
    script_service = _script_service

    # ── Step 1: Create container-bound script project ──────────────
    script_id = None
    for attempt in range(max_retries):
        try:
            _rate_limiter.acquire()
            project = script_service.projects().create(body={
                "title": "Puzzle Tools",
                "parentId": sheet_id,
            }).execute()
            script_id = project["scriptId"]
            debug_log(3, f"[{puzz_label}] Created script project {script_id}")
            break
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(3, f"[{puzz_label}] Rate limit creating script, waiting {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay * random.uniform(0.5, 1.5))
            else:
                debug_log(1, f"[{puzz_label}] Failed to create script project: {e}")
                return False
    else:
        debug_log(1, f"[{puzz_label}] EXHAUSTED retries creating script project")
        return False

    # ── Step 2: Push Apps Script code ───────────────────────────────
    for attempt in range(max_retries):
        try:
            _rate_limiter.acquire()
            script_service.projects().updateContent(
                scriptId=script_id,
                body={
                    "files": [
                        {"name": "Code", "type": "SERVER_JS",
                         "source": addon_code},
                        {"name": "appsscript", "type": "JSON",
                         "source": addon_manifest},
                    ]
                }
            ).execute()
            debug_log(3, f"[{puzz_label}] Pushed Apps Script code to script {script_id} ({len(addon_code)} chars)")
            break
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(3, f"[{puzz_label}] Rate limit pushing code, waiting {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay * random.uniform(0.5, 1.5))
            else:
                debug_log(1, f"[{puzz_label}] Failed to push script code: {e}")
                return False
    else:
        debug_log(1, f"[{puzz_label}] EXHAUSTED retries pushing script code")
        return False

    # ── Step 3: Pre-create _pb_activity sheet (hidden + protected) ─
    # Reuse the module-level sheetsservice instead of build()ing a new one.
    try:
        # Add the hidden sheet
        _rate_limiter.acquire()
        add_result = sheetsservice.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{
                "addSheet": {
                    "properties": {
                        "title": _ACTIVITY_SHEET_NAME,
                        "hidden": True,
                    }
                }
            }]}
        ).execute()

        activity_sheet_id = add_result["replies"][0]["addSheet"]["properties"]["sheetId"]

        # Write headers
        _rate_limiter.acquire()
        sheetsservice.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{_ACTIVITY_SHEET_NAME}!A1:C1",
            valueInputOption="RAW",
            body={"values": [["editor", "timestamp", "num_sheets"]]}
        ).execute()

        # Add warning-only protection
        _rate_limiter.acquire()
        sheetsservice.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{
                "addProtectedRange": {
                    "protectedRange": {
                        "range": {"sheetId": activity_sheet_id},
                        "description": "Managed by Puzzleboss — do not edit manually.",
                        "warningOnly": True,
                    }
                }
            }]}
        ).execute()

        debug_log(3, f"[{puzz_label}] Created hidden + protected _pb_activity sheet")

    except Exception as e:
        # Non-fatal — the onEdit trigger will create _pb_activity if missing
        debug_log(2, f"[{puzz_label}] Could not pre-create _pb_activity sheet: {e} "
                  "(trigger will create it on first edit)")

    debug_log(3, f"[{puzz_label}] Apps Script API activation complete (script_id={script_id})")
    return True


def _color_palette_cell_value():
    """Build a cell value with colored-space runs for the sheet color palette row."""
    # From https://sashamaps.net/docs/resources/20-colors/
    colors = [
        # Middle row
        "#e6194B",
        "#f58231",
        "#ffe119",
        "#bfef45",
        "#3cb44b",
        "#42d4f4",
        "#4363d8",
        "#911eb4",
        "#f032e6",
        # Darker tones
        "#800000",
        "#9A6324",
        "#808000",
        "#469990",
        "#000075",
        # Pastels
        "#fabed4",
        "#ffd8b1",
        "#fffac8",
        "#aaffc3",
        "#dcbeff",
    ]
    format_runs = []
    for idx, color in enumerate(colors):
        r, g, b = _hex_to_rgb_triple(color)
        format_runs.append(
            {
                "startIndex": idx,
                "format": {
                    "foregroundColorStyle": {
                        "rgbColor": {"red": r, "green": g, "blue": b},
                    },
                },
            }
        )
    # The string is made of spaces so that the colored text is invisible, just
    # to reduce visual distractions on the sheet.
    return {
        "userEnteredValue": {
            "stringValue": " " * len(colors),
        },
        "textFormatRuns": format_runs,
    }


def _hex_to_rgb_triple(hex_color):
    """Convert '#rrggbb' hex color to (r, g, b) floats in 0-1 range."""
    # hex_color is a hex code, with leading '#', e.g., '#abc123'
    hexes = hex_color[1:3], hex_color[3:5], hex_color[5:7]
    return tuple(int(x, base=16) / 255 for x in hexes)


def force_sheet_edit(driveid, mytimestamp=datetime.datetime.utcnow()):
    """Write a bigjimmybot probe timestamp to cell A7 to trigger edit detection."""
    debug_log(4, f"start with driveid: {driveid}")
    threadsafe_sheethttp = _get_thread_http()

    datarange = "A7"
    datainputoption = "USER_ENTERED"
    data = {"values": [[f"last bigjimmybot probe: {mytimestamp}"]]}
    _rate_limiter.acquire()
    response = (
        sheetsservice.spreadsheets()
        .values()
        .update(
            spreadsheetId=driveid,
            range=datarange,
            valueInputOption=datainputoption,
            body=data,
        )
        .execute(http=threadsafe_sheethttp)
    )
    debug_log(4, f"response to sheet edit attempt: {response}")
    return 0


def add_user_to_google(username, firstname, lastname, password, recovery_email=None):
    """Create a Google Workspace user account via Admin SDK. Returns 'OK' or error message."""
    debug_log(
        4,
        f"start with (username, firstname, lastname, password): {username} {firstname} {lastname} REDACTED",
    )
    msg = ""
    initadmin()

    userservice = build("admin", "directory_v1", credentials=admincreds)

    userbody = {
        "name": {"familyName": lastname, "givenName": firstname},
        "password": password,
        "primaryEmail": f"{username}@{configstruct['DOMAINNAME']}",
    }
    if recovery_email:
        userbody["recoveryEmail"] = recovery_email

    safe_body = {k: ("REDACTED" if k == "password" else v) for k, v in userbody.items()}
    debug_log(5, f"Attempting to add user with post body: {json.dumps(safe_body)}")
    try:
        _rate_limiter.acquire()
        addresponse = userservice.users().insert(body=userbody).execute()
    except googleapiclient.errors.HttpError as e:
        msg = json.loads(e.content)["error"]["message"]
        addresponse = None

    if not addresponse:
        errmsg = f"Error in adding user: {msg}"
        debug_log(1, errmsg)
        return errmsg

    debug_log(4, f"Created new google user {username}")
    return "OK"


def delete_google_user(username):
    """Delete a Google Workspace user account. Returns 'OK' or error message."""
    debug_log(4, f"start with username {username}")

    if configstruct.get("SKIP_GOOGLE_API") == "true":
        debug_log(3, "google user deletion skipped by config.")
        return "OK"

    initadmin()

    userservice = build("admin", "directory_v1", credentials=admincreds)
    email = f"{username}@{configstruct['DOMAINNAME']}"

    try:
        _rate_limiter.acquire()
        userservice.users().delete(userKey=email).execute()
    except googleapiclient.errors.HttpError as e:
        if e.resp.status == 404:
            debug_log(3, f"Google user {username} not found, nothing to delete")
            return "OK"
        msg = json.loads(e.content)["error"]["message"]
        errmsg = f"Error deleting Google user: {msg}"
        debug_log(1, errmsg)
        return errmsg

    return "OK"


def change_google_user_password(username, password):
    """Change a Google Workspace user's password. Returns 'OK' or error message."""
    debug_log(4, f"start with (username, password): {username} REDACTED")
    msg = ""
    initadmin()

    userservice = build("admin", "directory_v1", credentials=admincreds)
    email = f"{username}@{configstruct['DOMAINNAME']}"
    userbody = {"password": password, "primaryEmail": email}

    debug_log(
        5, f"Attempting to change user pass with post body: {json.dumps(userbody)}"
    )
    try:
        _rate_limiter.acquire()
        changeresponse = (
            userservice.users().update(userKey=email, body=userbody).execute()
        )
    except googleapiclient.errors.HttpError as e:
        msg = json.loads(e.content)["error"]["message"]
        changeresponse = None

    if not changeresponse:
        errmsg = f"Error in changing password: {msg}"
        debug_log(1, errmsg)
        return errmsg

    debug_log(4, f"Changed password for user {username}")

    return "OK"
