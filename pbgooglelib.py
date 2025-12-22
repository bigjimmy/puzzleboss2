import os.path
import sys
import time
import threading
import googleapiclient
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import google_auth_httplib2
import httplib2
import pblib
import datetime
import json
from pblib import *
from builtins import Exception

service = None
sheetsservice = None
creds = None
admincreds = None

# Thread-safe counter for quota failures (read by bigjimmybot for metrics)
quota_failure_count = 0
quota_failure_lock = threading.Lock()


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


def initadmin():
    debug_log(4, "start")

    global admincreds
    global ADMINSCOPES

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("admintoken.json"):
        debug_log(4, "Credentials found in admintoken.json.")
        admincreds = Credentials.from_authorized_user_file(
            "admintoken.json", ADMINSCOPES
        )
    # If there are no (valid) credentials available, let the user log in.
    if not admincreds or not admincreds.valid:
        if admincreds and admincreds.expired and admincreds.refresh_token:
            debug_log(3, "Refreshing credentials.")
            admincreds.refresh(Request())
        else:
            debug_log(0, "Admin Credentials missing. Run googleadmininit.py on console.")
            raise Exception("Google API admin credentials on server invalid or missing. Fatal error, contact puzztech immediately.")

        with open("admintoken.json", "w") as token:
            token.write(admincreds.to_json())


def initdrive():
    debug_log(4, "start")

    if configstruct["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google docs auth and init skipped by config.")
        return 0

    global service
    global sheetsservice
    global creds
    global SCOPES

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.json"):
        debug_log(4, "Credentials found in token.json.")
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            debug_log(3, "Refreshing credentials.")
            creds.refresh(Request())
        else:
            errmsg = "Credentials missing.  Run gdriveinit.py on console."
            debug_log(0, errmsg)
            sys.exit(255)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("drive", "v3", credentials=creds)
    sheetsservice = build("sheets", "v4", credentials=creds)
    debug_log(3, "Drive and Sheets services initialized")

    foldername = configstruct["HUNT_FOLDER_NAME"]

    # Check if hunt folder exists
    huntfoldercheck = (
        service.files()
        .list(
            fields="files(name), files(id)", spaces="drive", q="name='%s'" % foldername
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
        file = service.files().create(body=file_metadata, fields="id").execute()

        # Set global variable
        pblib.huntfolderid = file.get("id")
        debug_log(
            3,
            "New hunt root folder %s created with id %s"
            % (foldername, pblib.huntfolderid),
        )
    elif len(matchingfolders) > 1:
        errmsg = "Multiple folders found matching name %s! Fix this." % foldername
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


def get_puzzle_sheet_info(myfileid):
    """
    Get both revisions and sheet count for a puzzle spreadsheet in one call.
    Returns dict with 'revisions' (list) and 'sheetcount' (int or None).
    THREAD SAFE.
    Includes retry logic for rate limit (429) errors.
    """
    debug_log(5, "start with fileid: %s" % myfileid)
    
    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", 10))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", 5))
    
    result = {
        "revisions": [],
        "sheetcount": None
    }
    
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
            if type(retval) == str:
                debug_log(1, "Revisions API returned string (error) for %s: %s" % (myfileid, retval))
            else:
                all_revisions = retval.get("revisions", [])
                debug_log(5, "Revisions API returned %d total revisions for %s" % (len(all_revisions), myfileid))
                for revision in all_revisions:
                    last_user = revision.get("lastModifyingUser", {})
                    user_email = last_user.get("emailAddress", "unknown")
                    is_me = last_user.get("me", False)
                    debug_log(5, "Revision by %s (me=%s) at %s" % (user_email, is_me, revision.get("modifiedTime", "unknown")))
                    debug_log(5, "Full revision: %s" % revision)
                    if not is_me:
                        result["revisions"].append(revision)
                debug_log(5, "After filtering, %d revisions for %s" % (len(result["revisions"]), myfileid))
            revisions_success = True
            break  # Success, exit retry loop
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(3, "Rate limit hit fetching revisions for %s, waiting %d seconds (attempt %d/%d)" 
                          % (myfileid, retry_delay, attempt + 1, max_retries))
                time.sleep(retry_delay)
            else:
                debug_log(1, "Error fetching revisions for %s: %s" % (myfileid, e))
                break  # Non-rate-limit error, don't retry
    
    if not revisions_success and max_retries > 0:
        debug_log(1, "EXHAUSTED all %d retries fetching revisions for %s - giving up" % (max_retries, myfileid))
    
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
            debug_log(5, "Sheet count for %s: %s" % (myfileid, result["sheetcount"]))
            sheetcount_success = True
            break  # Success, exit retry loop
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                _increment_quota_failure()
                debug_log(3, "Rate limit hit getting sheet count for %s, waiting %d seconds (attempt %d/%d)" 
                          % (myfileid, retry_delay, attempt + 1, max_retries))
                time.sleep(retry_delay)
            else:
                debug_log(1, "Error getting sheet count for %s: %s" % (myfileid, e))
                break  # Non-rate-limit error, don't retry
    
    if not sheetcount_success and max_retries > 0:
        debug_log(1, "EXHAUSTED all %d retries getting sheet count for %s - giving up" % (max_retries, myfileid))
    
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

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", 10))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", 5))

    file = None
    for attempt in range(max_retries):
        try:
            file = service.files().create(body=file_metadata, fields="id").execute()
            debug_log(4, "folder id returned: %s" % file.get("id"))
            break  # Success
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                debug_log(3, "Rate limit hit creating round folder, waiting %d seconds (attempt %d/%d)" 
                          % (retry_delay, attempt + 1, max_retries))
                time.sleep(retry_delay)
            else:
                debug_log(0, "Error creating round folder: %s" % e)
                sys.exit(255)
    
    if file is None:
        debug_log(0, "EXHAUSTED all %d retries creating round folder - giving up" % max_retries)
        sys.exit(255)

    return file.get("id")

def delete_puzzle_sheet(sheetid):
    debug_log(4, "start delete with sheet id: %s" % sheetid)

    initdrive()

    body_value = {"trashed": True}

    try:
        response = (
            service.files()
            .update(fileId=sheetid, body=body_value)
            .execute()
            )

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

    max_retries = int(configstruct.get("BIGJIMMY_QUOTAFAIL_MAX_RETRIES", 10))
    retry_delay = int(configstruct.get("BIGJIMMY_QUOTAFAIL_DELAY", 5))

    # Create/copy file with retry logic
    file = None
    for attempt in range(max_retries):
        try:
            if configstruct["SHEETS_TEMPLATE_ID"] == "none":
                file = service.files().create(body=file_metadata, fields="id").execute()
                debug_log(4, "file ID returned from creation: %s" % file.get("id"))
            else:
                file = (
                    service.files()
                    .copy(
                        body=file_metadata,
                        fileId=configstruct["SHEETS_TEMPLATE_ID"],
                        fields="id",
                    )
                    .execute()
                )
                debug_log(4, "file ID returned from copy: %s" % file.get("id"))
            break  # Success
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                debug_log(3, "Rate limit hit creating file, waiting %d seconds (attempt %d/%d)" 
                          % (retry_delay, attempt + 1, max_retries))
                time.sleep(retry_delay)
            else:
                debug_log(0, "Error creating puzzle sheet file: %s" % e)
                sys.exit(255)
    
    if file is None:
        debug_log(0, "EXHAUSTED all %d retries creating puzzle sheet - giving up" % max_retries)
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
                "hideGridlines": true,
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
            if type(properties[key]) == dict:
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
                                "userEnteredFormat": {"bold": true},
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
                                "userEnteredFormat": {"bold": true},
                            },
                            {"userEnteredValue": {"stringValue": puzzledict["name"]}},
                        ]
                    },
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": "Puzzle URL:"},
                                "userEnteredFormat": {"bold": true},
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
                                "userEnteredFormat": {"bold": true},
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
                    {
                        "values": [
                            _color_palette_cell_value()
                        ]
                    },
                ],
            }
        }
    )

    body = {"requests": requests}

    debug_log(
        4, "Sheets api batchupdate request id: %s body %s" % (file.get("id"), body)
    )
    
    # Batch update with retry logic
    response = None
    for attempt in range(max_retries):
        try:
            response = (
                sheetsservice.spreadsheets()
                .batchUpdate(spreadsheetId=file.get("id"), body=body)
                .execute()
            )
            debug_log(5, "Response from sheetservice.spreadsheets.batchUpdate: %s" % response)
            break  # Success
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                debug_log(3, "Rate limit hit on batchUpdate, waiting %d seconds (attempt %d/%d)" 
                          % (retry_delay, attempt + 1, max_retries))
                time.sleep(retry_delay)
            else:
                debug_log(0, "Error in batchUpdate for puzzle sheet: %s" % e)
                sys.exit(255)
    
    if response is None:
        debug_log(0, "EXHAUSTED all %d retries on batchUpdate - giving up" % max_retries)
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
                service.permissions().create(fileId=file.get("id"), body=permission).execute()
            )
            debug_log(5, "Response from service.permissions.create: %s" % permresp)
            break  # Success
        except Exception as e:
            if "429" in str(e) or "RATE_LIMIT_EXCEEDED" in str(e):
                debug_log(3, "Rate limit hit setting permissions, waiting %d seconds (attempt %d/%d)" 
                          % (retry_delay, attempt + 1, max_retries))
                time.sleep(retry_delay)
            else:
                debug_log(0, "Error setting permissions for puzzle sheet: %s" % e)
                sys.exit(255)
    
    if permresp is None:
        debug_log(0, "EXHAUSTED all %d retries setting permissions - giving up" % max_retries)
        sys.exit(255)

    return file.get("id")


def _color_palette_cell_value():
    # From https://sashamaps.net/docs/resources/20-colors/
    colors = [
        # Middle row
        '#e6194B', '#f58231', '#ffe119', '#bfef45', '#3cb44b', '#42d4f4', '#4363d8', '#911eb4', '#f032e6',
        # Darker tones
        '#800000', '#9A6324', '#808000', '#469990', '#000075',
        # Pastels
        '#fabed4', '#ffd8b1', '#fffac8', '#aaffc3', '#dcbeff',
    ]
    format_runs = []
    for idx, color in enumerate(colors):
        r, g, b = _hex_to_rgb_triple(color)
        format_runs.append({
            "startIndex": idx,
            "format": {
                "foregroundColorStyle": {
                    "rgbColor": {"red": r, "green": g, "blue": b},
                },
            },
        })
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
    data = {"values": [["last bigjimmybot probe: %s" % mytimestamp]]}
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


def add_user_to_google(username, firstname, lastname, password):
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
        "primaryEmail": "%s@%s" % (username, configstruct["DOMAINNAME"]),
    }

    debug_log(5, "Attempting to add user with post body: %s" % json.dumps(userbody))
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
    initadmin()

    userservice = build("admin", "directory_v1", credentials=admincreds)
    email = "%s@%s" % (username, configstruct["DOMAINNAME"])

    changeresponse = userservice.users().delete(userKey=email).execute()
    return "OK"


def change_google_user_password(username, password):
    debug_log(4, "start with (username, password): %s REDACTED" % username)
    msg = ""
    initadmin()

    userservice = build("admin", "directory_v1", credentials=admincreds)
    email = "%s@%s" % (username, configstruct["DOMAINNAME"])
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
        errmsg = "Error in changing password: %s" % msg
        debug_log(1, errmsg)
        return errmsg

    debug_log(4, "Changed password for user %s" % username)

    return "OK"
