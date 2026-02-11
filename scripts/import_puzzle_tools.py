#!/usr/bin/env python3
"""
Import Jason Juang's Puzzle Tools add-on code into database config.

This script fetches the puzzle tools code from Jason's Apps Script project
and stores it in the APPS_SCRIPT_ADDON_CODE config value, enabling it to
be deployed to new puzzle sheets via the Apps Script API.

Usage:
  # Import from Jason's project (default)
  python3 scripts/import_puzzle_tools.py

  # Import from a different script project ID
  python3 scripts/import_puzzle_tools.py --script-id <PROJECT_ID>

  # Import from a local file
  python3 scripts/import_puzzle_tools.py --from-file scripts/puzzle_tools_addon.gs

Run in Docker:
  docker exec puzzleboss-app python3 /app/scripts/import_puzzle_tools.py
"""
import sys
import os
import argparse
import json

# Add parent directory to path to import pblib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pblib

# Jason's Puzzle Tools project ID
DEFAULT_SCRIPT_ID = "1Em58-E2Fxrx-Od0Jmcr-_88z8wAz-3MVNhytL-DchR_7slpsT2N219F2"


def get_credentials(subject='juang@importanthuntpoll.org'):
    """Get service account credentials with DWD to impersonate Jason."""
    sa_file = os.environ.get("SA_FILE", "service-account.json")
    if not os.path.exists(sa_file):
        print(f"❌ Service account file not found: {sa_file}")
        sys.exit(1)

    scopes = ['https://www.googleapis.com/auth/script.projects']
    creds = service_account.Credentials.from_service_account_file(
        sa_file, scopes=scopes, subject=subject
    )
    creds.refresh(Request())
    return creds


def extract_code_from_project(script_id):
    """Extract Apps Script code from a project."""
    print(f"📖 Extracting code from script project: {script_id}")

    creds = get_credentials()
    script_service = build('script', 'v1', credentials=creds)

    try:
        content = script_service.projects().getContent(scriptId=script_id).execute()
    except Exception as e:
        print(f"❌ Failed to extract code: {e}")
        sys.exit(1)

    files = content.get('files', [])
    print(f"✅ Found {len(files)} file(s) in project\n")

    code_file = None
    manifest_file = None

    for f in files:
        if f['type'] == 'SERVER_JS':
            code_file = f.get('source', '')
            print(f"  📄 Code file: {f['name']} ({len(code_file)} chars)")
        elif f['type'] == 'JSON' and f['name'] == 'appsscript':
            manifest_file = f.get('source', '')
            print(f"  📋 Manifest: {f['name']} ({len(manifest_file)} chars)")

    if not code_file:
        print("❌ No SERVER_JS code file found in project")
        sys.exit(1)

    return code_file, manifest_file or _get_default_manifest()


def _get_default_manifest():
    """Get default appsscript.json manifest."""
    return json.dumps({
        "timeZone": "America/New_York",
        "dependencies": {},
        "exceptionLogging": "STACKDRIVER",
        "runtimeVersion": "V8"
    })


def import_from_file(filepath):
    """Import code from a local file."""
    print(f"📖 Reading code from file: {filepath}")

    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        sys.exit(1)

    with open(filepath, 'r') as f:
        code = f.read()

    print(f"✅ Read {len(code)} characters from file")
    return code, _get_default_manifest()


def update_config(code, manifest):
    """Update the database config with the Apps Script code."""
    print("\n🔧 Updating database config...")

    # Initialize pblib and get config from YAML
    pblib.refresh_config()

    # Get database connection using Flask-MySQLdb (same as pbrest.py)
    from flask import Flask
    from flask_mysqldb import MySQL

    app = Flask(__name__)
    app.config['MYSQL_HOST'] = pblib.config['MYSQL']['HOST']
    app.config['MYSQL_USER'] = pblib.config['MYSQL']['USERNAME']
    app.config['MYSQL_PASSWORD'] = pblib.config['MYSQL']['PASSWORD']
    app.config['MYSQL_DB'] = pblib.config['MYSQL']['DATABASE']
    app.config['MYSQL_CHARSET'] = 'utf8mb4'

    mysql = MySQL(app)

    with app.app_context():
        conn = mysql.connection
        cursor = conn.cursor()

        # Update APPS_SCRIPT_ADDON_CODE
        cursor.execute(
            "INSERT INTO config (`key`, val) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE val = VALUES(val)",
            ('APPS_SCRIPT_ADDON_CODE', code)
        )

        # Update APPS_SCRIPT_ADDON_MANIFEST
        cursor.execute(
            "INSERT INTO config (`key`, val) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE val = VALUES(val)",
            ('APPS_SCRIPT_ADDON_MANIFEST', manifest)
        )

        conn.commit()
        cursor.close()

    print("✅ Config updated successfully!")
    print(f"   - APPS_SCRIPT_ADDON_CODE: {len(code)} chars")
    print(f"   - APPS_SCRIPT_ADDON_MANIFEST: {len(manifest)} chars")


def main():
    parser = argparse.ArgumentParser(
        description="Import Puzzle Tools add-on code into database config"
    )
    parser.add_argument(
        "--script-id",
        default=DEFAULT_SCRIPT_ID,
        help=f"Apps Script project ID (default: {DEFAULT_SCRIPT_ID})"
    )
    parser.add_argument(
        "--from-file",
        help="Import from a local .gs file instead of fetching from Google"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without updating the database"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Puzzle Tools Add-on Importer")
    print("=" * 70)
    print()

    if args.from_file:
        code, manifest = import_from_file(args.from_file)
    else:
        code, manifest = extract_code_from_project(args.script_id)

    if args.dry_run:
        print("\n" + "=" * 70)
        print("DRY RUN - No changes made")
        print("=" * 70)
        print(f"\nWould import {len(code)} chars of code and {len(manifest)} chars of manifest")
        print("\nPreview of code (first 500 chars):")
        print(code[:500])
        print("\n... (truncated)")
    else:
        update_config(code, manifest)

        print("\n" + "=" * 70)
        print("✅ Import Complete!")
        print("=" * 70)
        print("\nThe Puzzle Tools add-on will now be deployed to all new puzzle sheets.")
        print("Existing sheets can be updated by re-running puzzle creation or manually")
        print("deploying the script via the Apps Script API.")


if __name__ == "__main__":
    main()
