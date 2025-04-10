import os.path
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
creds = None
admincreds = None

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
            errmsg = "Admin Credentials missing.  Run googleadmininit.py on console."
            debug_log(0, errmsg)
            return {"error": errmsg}

        with open("admintoken.json", "w") as token:
            token.write(admincreds.to_json())


def initdrive():
    debug_log(4, "start")

    if configstruct["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google docs auth and init skipped by config.")
        return 0

    global service
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
            return {"error": errmsg}

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("drive", "v3", credentials=creds)

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
        return {"error": errmsg}
    else:
        debug_log(
            4,
            "Folder named %s found to already exist with id %s"
            % (foldername, matchingfolders[0]["id"]),
        )
        pblib.huntfolderid = matchingfolders[0]["id"]
    return 0


def get_revisions(myfileid):
    # will return full list of revisions for a google fileid not made by current user. THREAD SAFE

    debug_log(4, "start with fileid: %s" % myfileid)
    revisions = []
    threadsafe_http = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http())
    try:
        retval = (
            service.revisions()
            .list(fileId=myfileid, fields="*")
            .execute(http=threadsafe_http)
        )
    except Exception as e:
        debug_log(1, "Unknown Error fetching revisions for %s: %s" % (myfileid, e))
        return revisions

    if type(retval) == str:
        debug_log(1, "Problem fetching revisions for %s: %s" % (myfileid, retval))
        return revisions
    for revision in retval["revisions"]:
        # exclude revisions done by this bot
        debug_log(5, "Revision found: %s" % revision)
        if not (revision["lastModifyingUser"]["me"]):
            revisions.append(revision)
    return revisions


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

    file = service.files().create(body=file_metadata, fields="id").execute()

    debug_log(4, "folder id returned: %s" % file.get("id"))
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

    # Now let's set initial contents

    # Setup sheets service for this
    sheetsservice = build("sheets", "v4", credentials=creds)
    requests = []

    sheet_properties = {
        "metadata": {
            "sheetId": 1,
            "title": "Metadata",
            "gridProperties": {"rowCount": 7, "columnCount": 2},
            "index": 0,
        },
        "work": {
            "sheetId": 0,
            "title": "Work",
            "gridProperties": {"rowCount": 100, "columnCount": 26},
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
                            {"userEnteredValue": {"stringValue": "Round:"}},
                            {
                                "userEnteredValue": {
                                    "stringValue": puzzledict["roundname"]
                                }
                            },
                        ]
                    },
                    {
                        "values": [
                            {"userEnteredValue": {"stringValue": "Puzzle:"}},
                            {"userEnteredValue": {"stringValue": puzzledict["name"]}},
                        ]
                    },
                    {
                        "values": [
                            {"userEnteredValue": {"stringValue": "Actual Puzzle URL:"}},
                            {
                                "userEnteredValue": {
                                    "formulaValue": hyperlink(puzzledict["puzzle_uri"])
                                }
                            },
                        ]
                    },
                    {
                        "values": [
                            {"userEnteredValue": {"stringValue": "Chat URL:"}},
                            {
                                "userEnteredValue": {
                                    "formulaValue": hyperlink(
                                        puzzledict["chat_uri"],
                                        label="Discord channel #" + puzzledict["name"],
                                    )
                                }
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
    response = (
        sheetsservice.spreadsheets()
        .batchUpdate(spreadsheetId=file.get("id"), body=body)
        .execute()
    )
    permission = {
        "role": "writer",
        "type": "domain",
        "domain": configstruct["DOMAINNAME"],
    }
    debug_log(5, "Response from sheetservice.spreadsheets.batchUpdate: %s" % response)
    permresp = (
        service.permissions().create(fileId=file.get("id"), body=permission).execute()
    )
    debug_log(5, "Response from service.permissions.create: %s" % permresp)
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

    # Setup sheets service for this
    sheetsservice = build("sheets", "v4", credentials=creds)
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
