#!/usr/bin/env python3
"""
Extract Apps Script code from an existing sheet with a container-bound script.

This tool extracts the Apps Script code from a puzzle sheet (e.g., from HUNT2026 folder)
that has Jason Juang's Mystery Hunt Tools add-on installed, and outputs it in a format
suitable for storing in the APPS_SCRIPT_ADDON_CODE config value.

Usage:
  # Extract from a specific sheet
  python3 scripts/extract_addon_code.py --sheet-id <SHEET_ID>

  # Extract from a sheet URL
  python3 scripts/extract_addon_code.py --sheet-url "https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit"

  # Find sheets in HUNT2026 folder and list them
  python3 scripts/extract_addon_code.py --hunt-folder "HUNT2026"

Run in Docker:
  docker exec puzzleboss-app python3 /app/scripts/extract_addon_code.py --sheet-id <SHEET_ID>
"""
import sys
import os
import json
import argparse
import re

# Add parent directory to path to import pblib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Use the service account directly
SA_FILE = os.environ.get("SA_FILE", "service-account.json")
SUBJECT = os.environ.get("SUBJECT", "bigjimmy@importanthuntpoll.org")

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.projects",
]


def get_credentials():
    """Get service account credentials with DWD."""
    if not os.path.exists(SA_FILE):
        print(f"❌ Service account file not found: {SA_FILE}")
        sys.exit(1)

    creds = service_account.Credentials.from_service_account_file(
        SA_FILE, scopes=SCOPES, subject=SUBJECT
    )
    creds.refresh(Request())
    return creds


def extract_sheet_id(url_or_id):
    """Extract sheet ID from URL or return the ID if already an ID."""
    # If it's a URL, extract the ID
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url_or_id)
    if match:
        return match.group(1)
    # Otherwise assume it's already an ID
    return url_or_id


def list_hunt_sheets(folder_name):
    """List all sheets in a hunt folder."""
    print(f"Searching for sheets in folder: {folder_name}")
    creds = get_credentials()
    drive_service = build("drive", "v3", credentials=creds)

    # Find the folder
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
    results = drive_service.files().list(
        q=query,
        fields="files(id, name)",
        pageSize=10
    ).execute()

    folders = results.get("files", [])
    if not folders:
        print(f"❌ Folder '{folder_name}' not found")
        return

    folder_id = folders[0]["id"]
    print(f"✅ Found folder: {folders[0]['name']} ({folder_id})")

    # List sheets in the folder
    query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.spreadsheet'"
    results = drive_service.files().list(
        q=query,
        fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc",
        pageSize=20
    ).execute()

    sheets = results.get("files", [])
    if not sheets:
        print("❌ No sheets found in folder")
        return

    print(f"\n📊 Found {len(sheets)} sheets:")
    for i, sheet in enumerate(sheets, 1):
        print(f"  {i}. {sheet['name']}")
        print(f"     ID: {sheet['id']}")
        print(f"     URL: https://docs.google.com/spreadsheets/d/{sheet['id']}/edit")

    print("\nTo extract code from a sheet, run:")
    print(f"  python3 scripts/extract_addon_code.py --sheet-id <SHEET_ID>")


def extract_addon_code(sheet_id):
    """Extract Apps Script code from a sheet's container-bound script."""
    print(f"Extracting Apps Script code from sheet: {sheet_id}")
    creds = get_credentials()

    # Get sheet info
    drive_service = build("drive", "v3", credentials=creds)
    try:
        sheet_file = drive_service.files().get(
            fileId=sheet_id,
            fields="name"
        ).execute()
        sheet_name = sheet_file["name"]
        print(f"  Sheet name: {sheet_name}")
    except Exception as e:
        print(f"❌ Failed to get sheet info: {e}")
        sys.exit(1)

    # List scripts bound to this sheet
    script_service = build("script", "v1", credentials=creds)

    # Unfortunately, there's no direct API to list scripts by parent.
    # We need to get the script ID from the sheet's metadata.
    # The script is stored in Drive as a child of the sheet.

    query = f"'{sheet_id}' in parents and mimeType='application/vnd.google-apps.script'"
    try:
        results = drive_service.files().list(
            q=query,
            fields="files(id, name)",
            pageSize=10
        ).execute()

        scripts = results.get("files", [])
        if not scripts:
            print(f"❌ No container-bound script found on this sheet")
            print(f"   Make sure the sheet has the Mystery Hunt Tools add-on enabled")
            sys.exit(1)

        script_id = scripts[0]["id"]
        script_name = scripts[0]["name"]
        print(f"  ✅ Found script: {script_name} ({script_id})")

    except Exception as e:
        print(f"❌ Failed to find container-bound script: {e}")
        sys.exit(1)

    # Get the script content
    try:
        content = script_service.projects().getContent(scriptId=script_id).execute()
        files = content.get("files", [])

        print(f"\n📄 Found {len(files)} file(s) in the script:")

        code_files = []
        manifest_file = None

        for f in files:
            name = f["name"]
            ftype = f["type"]
            source = f.get("source", "")

            print(f"  - {name} ({ftype}, {len(source)} chars)")

            if ftype == "SERVER_JS":
                code_files.append({"name": name, "source": source})
            elif ftype == "JSON" and name == "appsscript":
                manifest_file = source

        if not code_files:
            print("❌ No SERVER_JS files found in the script")
            sys.exit(1)

        # Output the code in a format ready for config
        print("\n" + "=" * 70)
        print("📋 APPS SCRIPT CODE (ready for config)")
        print("=" * 70)

        if len(code_files) == 1:
            # Single file - output directly
            print("\nSingle code file found. Use this as APPS_SCRIPT_ADDON_CODE:\n")
            print(code_files[0]["source"])
        else:
            # Multiple files - need to handle differently
            print(f"\n⚠️  Multiple code files found ({len(code_files)})")
            print("The current system supports single-file scripts.")
            print("You may need to combine these files or modify the deployment logic.\n")
            for cf in code_files:
                print(f"\n--- {cf['name']} ---")
                print(cf["source"])
                print(f"--- End {cf['name']} ---\n")

        if manifest_file:
            print("\n" + "=" * 70)
            print("📋 MANIFEST (appsscript.json)")
            print("=" * 70)
            print(manifest_file)

        # Output JSON for programmatic use
        print("\n" + "=" * 70)
        print("📋 JSON FORMAT (for programmatic import)")
        print("=" * 70)
        output = {
            "code_files": code_files,
            "manifest": manifest_file,
            "source_sheet": sheet_id,
            "source_sheet_name": sheet_name,
            "script_id": script_id
        }
        print(json.dumps(output, indent=2))

    except Exception as e:
        print(f"❌ Failed to get script content: {e}")
        if "403" in str(e):
            print("   Make sure the service account has access to the sheet and script")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Extract Apps Script code from existing sheets"
    )
    parser.add_argument(
        "--sheet-id",
        help="Google Sheets ID to extract code from"
    )
    parser.add_argument(
        "--sheet-url",
        help="Google Sheets URL to extract code from"
    )
    parser.add_argument(
        "--hunt-folder",
        help="List sheets in a hunt folder (e.g., HUNT2026)"
    )

    args = parser.parse_args()

    if args.hunt_folder:
        list_hunt_sheets(args.hunt_folder)
    elif args.sheet_id:
        sheet_id = extract_sheet_id(args.sheet_id)
        extract_addon_code(sheet_id)
    elif args.sheet_url:
        sheet_id = extract_sheet_id(args.sheet_url)
        extract_addon_code(sheet_id)
    else:
        parser.print_help()
        print("\n❌ Error: Must specify --sheet-id, --sheet-url, or --hunt-folder")
        sys.exit(1)


if __name__ == "__main__":
    main()
