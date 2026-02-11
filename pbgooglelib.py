import os.path
import sys
import time
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
from pblib import *


service = None
sheetsservice = None
creds = None
admincreds = None

# Thread-safe counter for quota failures (read by bigjimmybot for metrics)
quota_failure_count = 0
quota_failure_lock = threading.Lock()

# Default retry/delay constants (can be overridden via config)
_DEFAULT_MAX_RETRIES = 10
_DEFAULT_RETRY_DELAY_SECONDS = 5


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
        debug_log(0, "Service account file not found: %s" % sa_file)
        raise Exception(
            "Service account key file '%s' not found. "
            "Download it from Google Cloud Console and place it in the app directory." % sa_file
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
    debug_log(4, "start")

    global admincreds
    global ADMINSCOPES

    sa_file = _get_service_account_file()
    subject = _get_impersonation_subject()

    debug_log(4, "Loading admin credentials from service account: %s (subject: %s)" % (sa_file, subject))
    admincreds = service_account.Credentials.from_service_account_file(
        sa_file, scopes=ADMINSCOPES, subject=subject
    )
    debug_log(3, "Admin credentials initialized via service account")


def initdrive():
    debug_log(4, "start")

    if configstruct["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google docs auth and init skipped by config.")
        return 0

    global service
    global sheetsservice
    global creds
    global SCOPES

    sa_file = _get_service_account_file()
    subject = _get_impersonation_subject()

    debug_log(4, "Loading Drive/Sheets credentials from service account: %s (subject: %s)" % (sa_file, subject))
    creds = service_account.Credentials.from_service_account_file(
        sa_file, scopes=SCOPES, subject=subject
    )

    service = build("drive", "v3", credentials=creds)
    sheetsservice = build("sheets", "v4", credentials=creds)
    debug_log(3, "Drive and Sheets services initialized via service account")

    foldername = configstruct["HUNT_FOLDER_NAME"]

    # Check if hunt folder exists
    huntfoldercheck = (
        service.files()
        .list(
            fields="files(name), files(id)", spaces="drive", q=f"name='{foldername}'"
        )
        .execute()
    )
    matchingfolders = huntfoldercheck.get("files", None)
    debug_log(5, "folder search result= %s" % matchingfolders)

    # Create initial hunt folder if it doesn't exist
    if not matchingfolders or matchingfolders == []:
        debug_log(3, "Folder named %s not found. Creating." % foldername)

        file_metadata = {
            "name": foldername,
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder_file = service.files().create(body=file_metadata, fields="id").execute()

        # Set global variable
        pblib.huntfolderid = folder_file.get("id")
        debug_log(
            3,
            "New hunt root folder %s created with id %s"
            % (foldername, pblib.huntfolderid),
        )
    elif len(matchingfolders) > 1:
        errmsg = f"Multiple folders found matching name {foldername}! Fix this."
        debug_log(0, errmsg)
        sys.exit(255)
    else:
        debug_log(
            4,
            "Folder named %s found to already exist with id %s"
            % (foldername, matchingfolders[0]["id"]),
        )
        pblib.huntfolderid = matchingfolders[0]["id"]
    return 0


def get_puzzle_sheet_info(myfileid, puzzlename=None):
    """
    Get editor activity metadata and sheet count for a puzzle spreadsheet.
    Returns dict with 'editors' (list of {solvername, timestamp}) and 'sheetcount' (int or None).

    All data is read from DeveloperMetadata in a single API call:
    - PB_ACTIVITY:<solvername> keys with values like '{"t": 1766277287}' (Unix timestamp)
    - PB_SPREADSHEET key with the sheet count value

    THREAD SAFE.
    Includes retry logic for rate limit (429) errors.

    Args:
        myfileid: Google Sheets file ID
        puzzlename: Optional puzzle name for logging
    """
    puzz_label = puzzlename if puzzlename else myfileid
    debug_log(5, "start for puzzle %s (fileid: %s)" % (puzz_label, myfileid))

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", _DEFAULT_MAX_RETRIES))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", _DEFAULT_RETRY_DELAY_SECONDS))

    result = {"editors": [], "sheetcount": None}

    if configstruct["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google API skipped by config.")
        return result

    # Create single threadsafe HTTP object for API calls
    threadsafe_http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http())

    # Get all metadata (editor activity + sheet count) in a single API call
    for attempt in range(max_retries):
        try:
            sheetsservice = build("sheets", "v4", credentials=creds)

            # Search for all spreadsheet-level metadata
            search_request = {
                "dataFilters": [
                    {"developerMetadataLookup": {"locationType": "SPREADSHEET"}}
                ]
            }

            response = (
                sheetsservice.spreadsheets()
                .developerMetadata()
                .search(spreadsheetId=myfileid, body=search_request)
                .execute(http=threadsafe_http)
            )

            matched_metadata = response.get("matchedDeveloperMetadata", [])
            debug_log(
                4,
                "[%s] DeveloperMetadata search returned %d items"
                % (puzz_label, len(matched_metadata)),
            )

            for item in matched_metadata:
                metadata = item.get("developerMetadata", {})
                key = metadata.get("metadataKey", "")
                value = metadata.get("metadataValue", "")
                debug_log(
                    4, "[%s] Metadata: key=%s value=%s" % (puzz_label, key, value)
                )

                # Look for PB_ACTIVITY:<solvername> keys
                if key.startswith("PB_ACTIVITY:"):
                    solvername = key[len("PB_ACTIVITY:") :]
                    try:
                        value_data = json.loads(value)
                        timestamp = value_data.get("t")
                        if timestamp:
                            result["editors"].append(
                                {
                                    "solvername": solvername,
                                    "timestamp": timestamp,  # Unix timestamp
                                }
                            )
                            debug_log(
                                4,
                                "[%s] Parsed editor activity: solver=%s timestamp=%s"
                                % (puzz_label, solvername, timestamp),
                            )
                    except json.JSONDecodeError as e:
                        debug_log(
                            2,
                            "[%s] Failed to parse metadata value for %s: %s"
                            % (puzz_label, key, e),
                        )

                # Look for PB_SPREADSHEET key for sheet count (value is JSON like {"num_sheets": 5})
                elif key == "PB_SPREADSHEET":
                    try:
                        value_data = json.loads(value)
                        result["sheetcount"] = int(value_data.get("num_sheets", 0))
                        debug_log(
                            4,
                            "[%s] Sheet count from metadata: %s"
                            % (puzz_label, result["sheetcount"]),
                        )
                    except (json.JSONDecodeError, ValueError, TypeError) as e:
                        debug_log(
                            2,
                            "[%s] Failed to parse sheet count from PB_SPREADSHEET: %s"
                            % (puzz_label, e),
                        )

            debug_log(
                5,
                "[%s] Found %d editors with activity, sheetcount=%s"
                % (puzz_label, len(result["editors"]), result["sheetcount"]),
            )
            break  # Success, exit retry loop

        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(
                    3,
                    "[%s] Rate limit hit fetching metadata, waiting %d seconds (attempt %d/%d)"
                    % (puzz_label, retry_delay, attempt + 1, max_retries),
                )
                time.sleep(retry_delay)
            else:
                debug_log(1, "[%s] Error fetching metadata: %s" % (puzz_label, e))
                break  # Non-rate-limit error, don't retry
    else:
        # Only reached if we exhausted all retries without breaking
        if max_retries > 0:
            debug_log(
                1,
                "[%s] EXHAUSTED all %d retries fetching metadata - giving up"
                % (puzz_label, max_retries),
            )

    return result


def check_developer_metadata_exists(myfileid, puzzlename=None):
    """
    Quick check to see if PuzzleBoss developer metadata exists on a sheet.
    Returns True if PB_ACTIVITY or PB_SPREADSHEET metadata is found, False otherwise.

    This is used to determine if the Chrome extension has been enabled for this sheet.

    THREAD SAFE.
    """
    puzz_label = puzzlename if puzzlename else myfileid
    debug_log(
        5,
        "Checking developer metadata existence for %s (fileid: %s)"
        % (puzz_label, myfileid),
    )

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", _DEFAULT_MAX_RETRIES))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", _DEFAULT_RETRY_DELAY_SECONDS))

    if configstruct["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google API skipped by config.")
        return False

    threadsafe_http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http())

    for attempt in range(max_retries):
        try:
            sheetsservice = build("sheets", "v4", credentials=creds)

            # Search for spreadsheet-level metadata
            search_request = {
                "dataFilters": [
                    {"developerMetadataLookup": {"locationType": "SPREADSHEET"}}
                ]
            }

            response = (
                sheetsservice.spreadsheets()
                .developerMetadata()
                .search(spreadsheetId=myfileid, body=search_request)
                .execute(http=threadsafe_http)
            )

            matched_metadata = response.get("matchedDeveloperMetadata", [])

            # Check if any PB_ keys exist
            for item in matched_metadata:
                metadata = item.get("developerMetadata", {})
                key = metadata.get("metadataKey", "")
                if key.startswith("PB_ACTIVITY:") or key == "PB_SPREADSHEET":
                    debug_log(
                        4, "[%s] Developer metadata found (key: %s)" % (puzz_label, key)
                    )
                    return True

            debug_log(4, "[%s] No PuzzleBoss developer metadata found" % puzz_label)
            return False

        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(
                    3,
                    "[%s] Rate limit hit checking metadata, waiting %d seconds (attempt %d/%d)"
                    % (puzz_label, retry_delay, attempt + 1, max_retries),
                )
                time.sleep(retry_delay)
            else:
                debug_log(
                    1, "[%s] Error checking metadata existence: %s" % (puzz_label, e)
                )
                return False

    debug_log(
        1,
        "[%s] EXHAUSTED all %d retries checking metadata - giving up"
        % (puzz_label, max_retries),
    )
    return False


def get_puzzle_sheet_info_activity(myfileid, puzzlename=None):
    """
    Get editor activity from the hidden '_pb_activity' sheet.
    Returns dict with 'editors' (list of {solvername, timestamp}) and 'sheetcount' (int or None).

    This is the Apps Script API approach: a simple onEdit trigger writes editor
    email, unix timestamp, and sheet count to a pre-created hidden sheet named
    '_pb_activity'. This function reads that data via the Sheets values API.

    The return format matches get_puzzle_sheet_info() so bigjimmybot can use
    either function interchangeably.

    Email-to-username conversion: strips the @domain portion from the email
    address to produce the puzzleboss username (e.g. 'alice@example.org' → 'alice').

    THREAD SAFE.
    Includes retry logic for rate limit (429) errors.

    Args:
        myfileid: Google Sheets file ID
        puzzlename: Optional puzzle name for logging
    """
    puzz_label = puzzlename if puzzlename else myfileid
    debug_log(5, "start _pb_activity read for puzzle %s (fileid: %s)" % (puzz_label, myfileid))

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", _DEFAULT_MAX_RETRIES))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", _DEFAULT_RETRY_DELAY_SECONDS))

    result = {"editors": [], "sheetcount": None}

    if configstruct["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google API skipped by config.")
        return result

    threadsafe_http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http())

    for attempt in range(max_retries):
        try:
            sheetsservice = build("sheets", "v4", credentials=creds)

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
                "[%s] _pb_activity returned %d rows (including header)"
                % (puzz_label, len(rows)),
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
                        "[%s] Invalid timestamp in _pb_activity row: %s"
                        % (puzz_label, row),
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
                    "[%s] Parsed editor activity: solver=%s timestamp=%s"
                    % (puzz_label, solvername, timestamp),
                )

            debug_log(
                5,
                "[%s] Found %d editors with activity, sheetcount=%s"
                % (puzz_label, len(result["editors"]), result["sheetcount"]),
            )
            break  # Success, exit retry loop

        except googleapiclient.errors.HttpError as e:
            if e.resp.status == 400 and "Unable to parse range" in str(e):
                # _pb_activity sheet doesn't exist yet (no one has edited)
                debug_log(
                    4,
                    "[%s] _pb_activity sheet not found (no edits yet)" % puzz_label,
                )
                break
            elif e.resp.status == 429 or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(
                    3,
                    "[%s] Rate limit hit reading _pb_activity, waiting %d seconds (attempt %d/%d)"
                    % (puzz_label, retry_delay, attempt + 1, max_retries),
                )
                time.sleep(retry_delay)
            else:
                debug_log(1, "[%s] Error reading _pb_activity: %s" % (puzz_label, e))
                break
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(
                    3,
                    "[%s] Rate limit hit reading _pb_activity, waiting %d seconds (attempt %d/%d)"
                    % (puzz_label, retry_delay, attempt + 1, max_retries),
                )
                time.sleep(retry_delay)
            else:
                debug_log(1, "[%s] Error reading _pb_activity: %s" % (puzz_label, e))
                break  # Non-rate-limit error, don't retry
    else:
        if max_retries > 0:
            debug_log(
                1,
                "[%s] EXHAUSTED all %d retries reading _pb_activity - giving up"
                % (puzz_label, max_retries),
            )

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
    debug_log(5, "start (legacy) for puzzle %s (fileid: %s)" % (puzz_label, myfileid))

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", _DEFAULT_MAX_RETRIES))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", _DEFAULT_RETRY_DELAY_SECONDS))

    result = {"revisions": [], "sheetcount": None}

    if configstruct["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google API skipped by config.")
        return result

    # Create single threadsafe HTTP object for both API calls
    threadsafe_http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http())

    # Get revisions from Drive API (with retry on rate limit)
    revisions_success = False
    for attempt in range(max_retries):
        try:
            retval = (
                service.revisions()
                .list(fileId=myfileid, fields="*")
                .execute(http=threadsafe_http)
            )
            if isinstance(retval, str):
                debug_log(
                    1,
                    "[%s] Revisions API returned string (error): %s"
                    % (puzz_label, retval),
                )
            else:
                all_revisions = retval.get("revisions", [])
                debug_log(
                    5,
                    "[%s] Revisions API returned %d total revisions"
                    % (puzz_label, len(all_revisions)),
                )
                for revision in all_revisions:
                    last_user = revision.get("lastModifyingUser", {})
                    is_me = last_user.get("me", False)
                    if not is_me:
                        result["revisions"].append(revision)
                debug_log(
                    5,
                    "[%s] After filtering, %d revisions"
                    % (puzz_label, len(result["revisions"])),
                )
            revisions_success = True
            break  # Success, exit retry loop
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(
                    3,
                    "[%s] Rate limit hit fetching revisions, waiting %d seconds (attempt %d/%d)"
                    % (puzz_label, retry_delay, attempt + 1, max_retries),
                )
                time.sleep(retry_delay)
            else:
                debug_log(1, "[%s] Error fetching revisions: %s" % (puzz_label, e))
                break  # Non-rate-limit error, don't retry

    if not revisions_success and max_retries > 0:
        debug_log(
            1,
            "[%s] EXHAUSTED all %d retries fetching revisions - giving up"
            % (puzz_label, max_retries),
        )

    # Get sheet count from Sheets API (with retry on rate limit)
    sheetcount_success = False
    for attempt in range(max_retries):
        try:
            sheetsservice = build("sheets", "v4", credentials=creds)
            spreadsheet = (
                sheetsservice.spreadsheets()
                .get(spreadsheetId=myfileid, fields="sheets.properties.title")
                .execute(http=threadsafe_http)
            )
            result["sheetcount"] = len(spreadsheet.get("sheets", []))
            debug_log(5, "[%s] Sheet count: %s" % (puzz_label, result["sheetcount"]))
            sheetcount_success = True
            break  # Success, exit retry loop
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(
                    3,
                    "[%s] Rate limit hit getting sheet count, waiting %d seconds (attempt %d/%d)"
                    % (puzz_label, retry_delay, attempt + 1, max_retries),
                )
                time.sleep(retry_delay)
            else:
                debug_log(1, "[%s] Error getting sheet count: %s" % (puzz_label, e))
                break  # Non-rate-limit error, don't retry

    if not sheetcount_success and max_retries > 0:
        debug_log(
            1,
            "[%s] EXHAUSTED all %d retries getting sheet count - giving up"
            % (puzz_label, max_retries),
        )

    return result


def create_round_folder(foldername):
    debug_log(4, "start with foldername: %s" % foldername)

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
            folder_file = service.files().create(body=file_metadata, fields="id").execute()
            debug_log(4, "folder id returned: %s" % folder_file.get("id"))
            break  # Success
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                debug_log(
                    3,
                    "Rate limit hit creating round folder, waiting %d seconds (attempt %d/%d)"
                    % (retry_delay, attempt + 1, max_retries),
                )
                time.sleep(retry_delay)
            else:
                debug_log(0, "Error creating round folder: %s" % e)
                sys.exit(255)

    if folder_file is None:
        debug_log(
            0,
            "EXHAUSTED all %d retries creating round folder - giving up" % max_retries,
        )
        sys.exit(255)

    return folder_file.get("id")


def delete_puzzle_sheet(sheetid):
    debug_log(4, "start delete with sheet id: %s" % sheetid)

    initdrive()

    body_value = {"trashed": True}

    try:
        service.files().update(fileId=sheetid, body=body_value).execute()

    except Exception as e:
        debug_log(1, "Delete failed for sheet %s. Error is %s." % (sheetid, e))
        return 255

    return 0


def create_puzzle_sheet(parentfolder, puzzledict):
    debug_log(
        4, "start with parentfolder: %s, puzzledict %s" % (parentfolder, puzzledict)
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
            if configstruct["SHEETS_TEMPLATE_ID"] == "none":
                sheet_file = service.files().create(body=file_metadata, fields="id").execute()
                debug_log(4, "file ID returned from creation: %s" % sheet_file.get("id"))
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
                debug_log(4, "file ID returned from copy: %s" % sheet_file.get("id"))
            break  # Success
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                debug_log(
                    3,
                    "Rate limit hit creating file, waiting %d seconds (attempt %d/%d)"
                    % (retry_delay, attempt + 1, max_retries),
                )
                time.sleep(retry_delay)
            else:
                debug_log(0, "Error creating puzzle sheet file: %s" % e)
                sys.exit(255)

    if sheet_file is None:
        debug_log(
            0,
            "EXHAUSTED all %d retries creating puzzle sheet - giving up" % max_retries,
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
        4, "Sheets api batchupdate request id: %s body %s" % (sheet_file.get("id"), body)
    )

    # Batch update with retry logic
    response = None
    for attempt in range(max_retries):
        try:
            response = (
                sheetsservice.spreadsheets()
                .batchUpdate(spreadsheetId=sheet_file.get("id"), body=body)
                .execute()
            )
            debug_log(
                5, "Response from sheetservice.spreadsheets.batchUpdate: %s" % response
            )
            break  # Success
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                debug_log(
                    3,
                    "Rate limit hit on batchUpdate, waiting %d seconds (attempt %d/%d)"
                    % (retry_delay, attempt + 1, max_retries),
                )
                time.sleep(retry_delay)
            else:
                debug_log(0, "Error in batchUpdate for puzzle sheet: %s" % e)
                sys.exit(255)

    if response is None:
        debug_log(
            0, "EXHAUSTED all %d retries on batchUpdate - giving up" % max_retries
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
            permresp = (
                service.permissions()
                .create(fileId=sheet_file.get("id"), body=permission)
                .execute()
            )
            debug_log(5, "Response from service.permissions.create: %s" % permresp)
            break  # Success
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                debug_log(
                    3,
                    "Rate limit hit setting permissions, waiting %d seconds (attempt %d/%d)"
                    % (retry_delay, attempt + 1, max_retries),
                )
                time.sleep(retry_delay)
            else:
                debug_log(0, "Error setting permissions for puzzle sheet: %s" % e)
                sys.exit(255)

    if permresp is None:
        debug_log(
            0, "EXHAUSTED all %d retries setting permissions - giving up" % max_retries
        )
        sys.exit(255)

    return sheet_file.get("id")


# ── Apps Script code pushed to container-bound script projects ──────
# This is the simple onEdit trigger that writes editor activity to a
# hidden '_pb_activity' sheet. It's pushed to each puzzle sheet when
# activate_puzzle_sheet_via_api() is called with no custom code configured.
#
# Why hidden sheet instead of DeveloperMetadata?
# Simple triggers can write to sheets without authorization, but
# DeveloperMetadata operations require authorized access. The hidden
# sheet approach allows activity tracking to work without any user
# authorization prompts.
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
      - APPS_SCRIPT_ADDON_CODE: The Apps Script code to deploy (falls back to
        default onEdit activity tracker if not set)
      - APPS_SCRIPT_ADDON_MANIFEST: The appsscript.json manifest (falls back
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
    debug_log(4, "[%s] activate_puzzle_sheet_via_api start (sheet_id: %s)"
              % (puzz_label, sheet_id))

    if configstruct.get("SKIP_GOOGLE_API") == "true":
        debug_log(3, "[%s] Skipping API activation (SKIP_GOOGLE_API)" % puzz_label)
        return False

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", _DEFAULT_MAX_RETRIES))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", _DEFAULT_RETRY_DELAY_SECONDS))

    # Get the Apps Script code to deploy (configurable or default)
    addon_code = configstruct.get("APPS_SCRIPT_ADDON_CODE", "").strip()
    addon_manifest = configstruct.get("APPS_SCRIPT_ADDON_MANIFEST", "").strip()

    if not addon_code:
        addon_code = _APPS_SCRIPT_ONEDIT_CODE
        debug_log(4, "[%s] Using default onEdit activity tracker" % puzz_label)
    else:
        debug_log(3, "[%s] Using custom Apps Script code from config (APPS_SCRIPT_ADDON_CODE)"
                  % puzz_label)

    if not addon_manifest:
        addon_manifest = _APPS_SCRIPT_MANIFEST
    else:
        # Validate manifest is parseable JSON
        try:
            json.loads(addon_manifest)
        except json.JSONDecodeError as e:
            debug_log(1, "[%s] APPS_SCRIPT_ADDON_MANIFEST is invalid JSON (%s), using default"
                      % (puzz_label, e))
            addon_manifest = _APPS_SCRIPT_MANIFEST

    # Need script.projects scope — create new credentials with it
    sa_file = _get_service_account_file()
    subject = _get_impersonation_subject()
    if not sa_file or not subject:
        debug_log(1, "[%s] Cannot activate via API — service account not configured"
                  % puzz_label)
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
    except Exception as e:
        debug_log(1, "[%s] Failed to create API credentials: %s" % (puzz_label, e))
        return False

    # ── Step 1: Create container-bound script project ──────────────
    script_id = None
    for attempt in range(max_retries):
        try:
            script_service = build("script", "v1", credentials=api_creds)
            project = script_service.projects().create(body={
                "title": "Puzzle Tools",
                "parentId": sheet_id,
            }).execute()
            script_id = project["scriptId"]
            debug_log(3, "[%s] Created script project %s" % (puzz_label, script_id))
            break
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(3, "[%s] Rate limit creating script, waiting %ds (attempt %d/%d)"
                          % (puzz_label, retry_delay, attempt + 1, max_retries))
                time.sleep(retry_delay)
            else:
                debug_log(1, "[%s] Failed to create script project: %s" % (puzz_label, e))
                return False
    else:
        debug_log(1, "[%s] EXHAUSTED retries creating script project" % puzz_label)
        return False

    # ── Step 2: Push Apps Script code ───────────────────────────────
    for attempt in range(max_retries):
        try:
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
            debug_log(3, "[%s] Pushed Apps Script code to script %s (% chars)"
                      % (puzz_label, script_id, len(addon_code)))
            break
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(3, "[%s] Rate limit pushing code, waiting %ds (attempt %d/%d)"
                          % (puzz_label, retry_delay, attempt + 1, max_retries))
                time.sleep(retry_delay)
            else:
                debug_log(1, "[%s] Failed to push script code: %s" % (puzz_label, e))
                return False
    else:
        debug_log(1, "[%s] EXHAUSTED retries pushing script code" % puzz_label)
        return False

    # ── Step 3: Pre-create _pb_activity sheet (hidden + protected) ─
    # Only needed for the default tracker (not the full puzzle tools).
    # The full puzzle tools use DeveloperMetadata and don't need this sheet.
    try:
        sheets_service = build("sheets", "v4", credentials=api_creds)

        # Add the hidden sheet
        add_result = sheets_service.spreadsheets().batchUpdate(
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
        sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"{_ACTIVITY_SHEET_NAME}!A1:C1",
            valueInputOption="RAW",
            body={"values": [["editor", "timestamp", "num_sheets"]]}
        ).execute()

        # Add warning-only protection
        sheets_service.spreadsheets().batchUpdate(
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

        debug_log(3, "[%s] Created hidden + protected _pb_activity sheet" % puzz_label)

    except Exception as e:
        # Non-fatal — the onEdit trigger will create _pb_activity if missing
        debug_log(2, "[%s] Could not pre-create _pb_activity sheet: %s "
                  "(trigger will create it on first edit)" % (puzz_label, e))

    debug_log(3, "[%s] Apps Script API activation complete (script_id=%s)"
              % (puzz_label, script_id))
    return True


def _color_palette_cell_value():
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
    # hex_color is a hex code, with leading '#', e.g., '#abc123'
    hexes = hex_color[1:3], hex_color[3:5], hex_color[5:7]
    return tuple(int(x, base=16) / 255 for x in hexes)


def force_sheet_edit(driveid, mytimestamp=datetime.datetime.utcnow()):
    debug_log(4, "start with driveid: %s" % driveid)
    threadsafe_sheethttp = google_auth_httplib2.AuthorizedHttp(
        creds, http=httplib2.Http()
    )

    datarange = "A7"
    datainputoption = "USER_ENTERED"
    data = {"values": [[f"last bigjimmybot probe: {mytimestamp}"]]}
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
    debug_log(4, "response to sheet edit attempt: %s" % response)
    return 0


def add_user_to_google(username, firstname, lastname, password, recovery_email=None):
    debug_log(
        4,
        "start with (username, firstname, lastname, password): %s %s %s REDACTED"
        % (username, firstname, lastname),
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
    debug_log(5, "Attempting to add user with post body: %s" % json.dumps(safe_body))
    try:
        addresponse = userservice.users().insert(body=userbody).execute()
    except googleapiclient.errors.HttpError as e:
        msg = json.loads(e.content)["error"]["message"]
        addresponse = None

    if not addresponse:
        errmsg = "Error in adding user: %s" % msg
        debug_log(1, errmsg)
        return errmsg

    debug_log(4, "Created new google user %s" % username)
    return "OK"


def delete_google_user(username):
    debug_log(4, "start with username %s" % username)

    if configstruct.get("SKIP_GOOGLE_API") == "true":
        debug_log(3, "google user deletion skipped by config.")
        return "OK"

    initadmin()

    userservice = build("admin", "directory_v1", credentials=admincreds)
    email = f"{username}@{configstruct['DOMAINNAME']}"

    try:
        userservice.users().delete(userKey=email).execute()
    except googleapiclient.errors.HttpError as e:
        if e.resp.status == 404:
            debug_log(3, "Google user %s not found, nothing to delete" % username)
            return "OK"
        msg = json.loads(e.content)["error"]["message"]
        errmsg = f"Error deleting Google user: {msg}"
        debug_log(1, errmsg)
        return errmsg

    return "OK"


def change_google_user_password(username, password):
    debug_log(4, "start with (username, password): %s REDACTED" % username)
    msg = ""
    initadmin()

    userservice = build("admin", "directory_v1", credentials=admincreds)
    email = f"{username}@{configstruct['DOMAINNAME']}"
    userbody = {"password": password, "primaryEmail": email}

    debug_log(
        5, "Attempting to change user pass with post body: %s" % json.dumps(userbody)
    )
    try:
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

    debug_log(4, "Changed password for user %s" % username)

    return "OK"
