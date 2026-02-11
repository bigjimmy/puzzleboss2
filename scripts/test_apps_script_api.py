#!/usr/bin/env python3
"""
Test whether the Apps Script API works with our DWD service account.

Tests:
1. Create a temp spreadsheet via Sheets API
2. projects.create — create a container-bound script on it
3. projects.updateContent — push a simple onEdit trigger
4. Verify by reading back the project

Run in Docker:
  docker exec puzzleboss-app python3 /app/scripts/test_apps_script_api.py
"""
import sys
import os
import json

# Use the service account directly (no pblib dependency on config DB)
SA_FILE = os.environ.get("SA_FILE", "service-account.json")
SUBJECT = os.environ.get("SUBJECT", "bigjimmy@importanthuntpoll.org")

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/script.projects",
]

from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

print(f"Service account: {SA_FILE}")
print(f"Impersonating: {SUBJECT}")

creds = service_account.Credentials.from_service_account_file(
    SA_FILE, scopes=SCOPES, subject=SUBJECT
)
creds.refresh(Request())
print(f"Access token: {creds.token[:40]}...")

# ── Step 0: Create a temporary test spreadsheet ───────────────────
print()
print("=" * 60)
print("Step 0: Creating a temporary test spreadsheet")
print("=" * 60)

sheets_service = build("sheets", "v4", credentials=creds)
body = {"properties": {"title": "PB_APPS_SCRIPT_TEST (delete me)"}}
sheet = sheets_service.spreadsheets().create(body=body).execute()
sheet_id = sheet["spreadsheetId"]
print(f"  ✅ Created test sheet: {sheet_id}")
print(f"  URL: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")

# ── Step 1: Create container-bound script project ──────────────────
print()
print("=" * 60)
print("Step 1: projects.create (container-bound script)")
print("=" * 60)

try:
    script_service = build("script", "v1", credentials=creds)

    create_body = {
        "title": "PB Activity Tracker",
        "parentId": sheet_id,
    }

    project = script_service.projects().create(body=create_body).execute()
    script_id = project["scriptId"]
    print(f"  ✅ SUCCESS: Created script project!")
    print(f"  Script ID: {script_id}")
    print(f"  Parent ID: {project.get('parentId', 'N/A')}")
    print(f"  Title: {project.get('title', 'N/A')}")

except Exception as e:
    print(f"  ❌ FAILED: {type(e).__name__}: {e}")
    if hasattr(e, "content"):
        print(f"  Response: {e.content.decode('utf-8', errors='replace')[:500]}")
    print()
    print("  If you see 'Insufficient Permission', ensure this scope is in DWD config:")
    print("  https://www.googleapis.com/auth/script.projects")
    print()
    print("  If you see 'Apps Script API has not been used', enable it at:")
    print("  https://console.cloud.google.com/apis/api/script.googleapis.com")
    sys.exit(1)

# ── Step 2: Push code via projects.updateContent ───────────────────
print()
print("=" * 60)
print("Step 2: projects.updateContent (push simple onEdit trigger)")
print("=" * 60)

# Simple onEdit trigger that writes activity to a hidden sheet.
# Simple triggers need NO authorization — they fire automatically.
apps_script_code = r"""
/**
 * PB Activity Tracker — simple onEdit trigger.
 * Writes editor activity to a hidden '_pb_activity' sheet.
 * No authorization required (runs as simple trigger).
 */

var ACTIVITY_SHEET_NAME = '_pb_activity';

/**
 * Simple trigger — fires on every manual edit.
 * Records the editor's email and Unix timestamp.
 */
function onEdit(e) {
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var actSheet = ss.getSheetByName(ACTIVITY_SHEET_NAME);

    // Create the activity sheet if it doesn't exist
    if (!actSheet) {
      actSheet = ss.insertSheet(ACTIVITY_SHEET_NAME);
      actSheet.hideSheet();
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
    var numSheets = ss.getSheets().length;

    // Update or insert editor row
    var data = actSheet.getDataRange().getValues();
    var found = false;
    for (var i = 1; i < data.length; i++) {
      if (data[i][0] === editor) {
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

manifest = json.dumps({
    "timeZone": "America/New_York",
    "exceptionLogging": "STACKDRIVER",
    "runtimeVersion": "V8",
})

update_body = {
    "files": [
        {
            "name": "Code",
            "type": "SERVER_JS",
            "source": apps_script_code,
        },
        {
            "name": "appsscript",
            "type": "JSON",
            "source": manifest,
        },
    ]
}

try:
    result = (
        script_service.projects()
        .updateContent(scriptId=script_id, body=update_body)
        .execute()
    )
    print(f"  ✅ SUCCESS: Pushed code to script project!")
    for f in result.get("files", []):
        print(f"    File: {f['name']} ({f['type']}, {len(f.get('source', ''))} chars)")

except Exception as e:
    print(f"  ❌ FAILED: {type(e).__name__}: {e}")
    if hasattr(e, "content"):
        print(f"  Response: {e.content.decode('utf-8', errors='replace')[:500]}")

# ── Step 3: Verify by reading back ─────────────────────────────────
print()
print("=" * 60)
print("Step 3: projects.getContent (verify)")
print("=" * 60)

try:
    content = (
        script_service.projects()
        .getContent(scriptId=script_id)
        .execute()
    )
    for f in content.get("files", []):
        src = f.get("source", "")
        print(f"  File: {f['name']} ({f['type']}, {len(src)} chars)")
        if f["name"] == "Code":
            # Show first few lines to confirm
            lines = src.strip().split("\n")[:5]
            for line in lines:
                print(f"    | {line}")
            print(f"    | ... ({len(src.strip().split(chr(10)))} lines total)")
    print(f"  ✅ Script project verified!")

except Exception as e:
    print(f"  ❌ FAILED: {type(e).__name__}: {e}")

# ── Summary ────────────────────────────────────────────────────────
print()
print("=" * 60)
print("Summary")
print("=" * 60)
print(f"  Sheet: https://docs.google.com/spreadsheets/d/{sheet_id}/edit")
print(f"  Script ID: {script_id}")
print()
print("  To test the simple trigger:")
print("  1. Open the sheet URL above in your browser")
print("  2. Edit any cell (type something and press Enter)")
print("  3. Check for the hidden '_pb_activity' sheet:")
print("     - Right-click any sheet tab → 'Show hidden sheets'")
print("     - Or check via the Sheets API (see below)")
print()
print("  To check '_pb_activity' via Sheets API, run:")
print(f"  docker exec puzzleboss-app python3 -c \"")
print(f"from googleapiclient.discovery import build")
print(f"from google.oauth2 import service_account")
print(f"from google.auth.transport.requests import Request")
print(f"c = service_account.Credentials.from_service_account_file(")
print(f"    '{SA_FILE}', scopes=['https://www.googleapis.com/auth/spreadsheets'],")
print(f"    subject='{SUBJECT}')")
print(f"c.refresh(Request())")
print(f"s = build('sheets', 'v4', credentials=c)")
print(f"r = s.spreadsheets().values().get(spreadsheetId='{sheet_id}',")
print(f"    range='_pb_activity!A:C').execute()")
print(f"print(r.get('values', []))\"")
print()
print("  To clean up (delete the test sheet):")
print(f"  docker exec puzzleboss-app python3 -c \"")
print(f"from googleapiclient.discovery import build")
print(f"from google.oauth2 import service_account")
print(f"from google.auth.transport.requests import Request")
print(f"c = service_account.Credentials.from_service_account_file(")
print(f"    '{SA_FILE}', scopes=['https://www.googleapis.com/auth/drive'],")
print(f"    subject='{SUBJECT}')")
print(f"c.refresh(Request())")
print(f"d = build('drive', 'v3', credentials=c)")
print(f"d.files().delete(fileId='{sheet_id}').execute()")
print(f"print('Deleted')\"")
print()
print("=" * 60)
print("Done.")
print("=" * 60)
