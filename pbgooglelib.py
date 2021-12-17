import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import google_auth_httplib2
import httplib2
import pblib
import datetime
from pblib import *
from builtins import Exception

service = None
creds = None
SCOPES = [
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.appdata",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/admin.directory.user",
]


def initdrive():
    debug_log(4, "start")

    if config["GOOGLE"]["SKIP_GOOGLE_API"] == "true":
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

    foldername = config["GOOGLE"]["HUNT_FOLDER_NAME"]

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

    if config["GOOGLE"]["SKIP_GOOGLE_API"] == "true":
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


def create_puzzle_sheet(parentfolder, puzzledict):
    debug_log(
        4, "start with parentfolder: %s, puzzledict %s" % (parentfolder, puzzledict)
    )
    name = puzzledict["name"]

    if config["GOOGLE"]["SKIP_GOOGLE_API"] == "true":
        debug_log(3, "google puzzle creation skipped by config.")
        return "xxxskippedbyconfigxxx"

    initdrive()

    file_metadata = {
        "name": name,
        "parents": [parentfolder],
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }

    file = service.files().create(body=file_metadata, fields="id").execute()
    debug_log(4, "file ID returned: %s" % file.get("id"))

    # Now let's set initial contents

    # Setup sheets service for this
    sheetsservice = build("sheets", "v4", credentials=creds)
    requests = []

    # Create new page
    requests.append(
        {
            "addSheet": {
                "properties": {
                    "title": "%s metadata" % name,
                    "gridProperties": {"rowCount": 7, "columnCount": 2},
                    "index": 0,
                    "sheetId": 1,
                }
            }
        }
    )

    # Relabel existing sheet as "Work" and setup appropriately
    requests.append(
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": 0,
                    "title": "Work on %s" % name,
                    "gridProperties": {"rowCount": 100, "columnCount": 26},
                    "index": 2,
                },
                "fields": "title,gridProperties.rowCount,gridProperties.columnCount,index",
            }
        }
    )

    # Set format of new metadata sheet
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

    # Set content of new metadata sheet
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
                "fields": "userEnteredValue, effectiveValue",
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
                                    "stringValue": puzzledict["puzzle_uri"]
                                }
                            },
                        ]
                    },
                    {
                        "values": [
                            {"userEnteredValue": {"stringValue": "Chat URL:"}},
                            {
                                "userEnteredValue": {
                                    "stringValue": puzzledict["chat_uri"]
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
        "domain": config["GOOGLE"]["DOMAINNAME"],
    }
    debug_log(5, "Response from sheetservice.spreadsheets.batchUpdate: %s" % response)
    permresp = (
        service.permissions().create(fileId=file.get("id"), body=permission).execute()
    )
    debug_log(5, "Response from service.permissions.create: %s" % permresp)
    return file.get('id')

def force_sheet_edit(driveid, mytimestamp = datetime.datetime.utcnow()):
    debug_log(4, "start with driveid: %s" % driveid)
    threadsafe_sheethttp = google_auth_httplib2.AuthorizedHttp(creds, http=httplib2.Http())
    
    # Setup sheets service for this
    sheetsservice = build('sheets', 'v4', credentials=creds)
    datarange="A7"
    datainputoption="USER_ENTERED"
    data = { "values" : [["last bigjimmybot probe: %s" % mytimestamp]]}
    response = sheetsservice.spreadsheets().values().update(spreadsheetId=driveid, range=datarange, valueInputOption=datainputoption, body=data).execute(http=threadsafe_sheethttp)
    debug_log(4, "response to sheet edit attempt: %s" % response)
    return(0)

def add_user_to_google(username, firstname, lastname, password):
    debug_log(4, "start with (username, firstname, lastname, password): %s %s %s REDACTED" % (username, firstname, lastname))
    userservice = build('admin', 'directory_v1', credentials=creds)

    userbody = { "name" : { 
                            "familyName" : lastname,
                            "givenName" : firstname 
                          },
                 "password" : password,
                 "primaryEmail" : "%s@%s" % (username, config["GOOGLE"]["DOMAINNAME"])
                }
    
    debug_log(5, "Attempting to add user with post body: %s" % json.dumps(userbody))    
    addresponse = service.users().insert(body=userbody).execute()
    
    if not addresponse:
        errmsg = "Error in adding user!"
        debug_log(1, errmsg)
        return errmsg   
    
    return("OK")

def change_google_user_password(username, password):
    debug_log(4, "start with (username, password): %s REDACTED" % username)
    userservice = build('admin', 'directory_v1', credentials=creds)
    email = "%s@%s" % (username, config["GOOGLE"]["DOMAINNAME"])
    userbody = { "password" : password, "primaryEmail" : email }
    
    debug_log(5, "Attempting to change user pass with post body: %s" % json.dumps(userbody))
    changeresponse = service.users().update(userKey=email, body=userbody),execute()
    
    if not changeresponse:
        errmsg = "Error in changing password for user!"
        debug_log(1, errmsg)
        return errmsg
    
    return("OK")   

    
        

    
