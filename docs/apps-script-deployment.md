# Apps Script Deployment System

## Overview

Puzzleboss deploys a customizable Apps Script add-on to puzzle sheets using the **Google Apps Script API**. This replaces the previous cookie-based `/scripts/invoke` method with a more maintainable, API-driven approach.

The deployed add-on provides:
- **Activity Tracking**: Records solver activity for bigjimmybot via hidden `_pb_activity` sheet
- **Puzzle Tools**: Grid manipulation (symmetry, crossword formatting, hex grids, tab creation)

## Architecture

```
Puzzle Creation Flow:
  addpuzzle.php (UI)  →  pbrest.py  →  pbgooglelib.activate_puzzle_sheet_via_api()
                                        ├── Creates container-bound Apps Script project
                                        ├── Deploys code from APPS_SCRIPT_ADDON_CODE config
                                        └── Creates hidden _pb_activity sheet

Activity Tracking Flow:
  User edits cell  →  Apps Script onEdit trigger  →  Writes to hidden _pb_activity sheet
                                                      (email, timestamp, num_sheets)
  bigjimmybot.py   →  get_puzzle_sheet_info_activity()  →  Reads via Sheets API
```

## Configuration

### Database Config Values

| Key | Description | Default |
|-----|-------------|---------|
| `APPS_SCRIPT_ADDON_CODE` | The Apps Script code to deploy (JavaScript) | Falls back to simple onEdit tracker |
| `APPS_SCRIPT_ADDON_MANIFEST` | The appsscript.json manifest | Default V8 runtime config |

### Add-on Code

The add-on code is stored in the `APPS_SCRIPT_ADDON_CODE` database config value:

**Current Implementation** (based on **dannybd/sheets-puzzleboss-tools**)
- Puzzle-solving utilities (symmetry, formatting, tab creation, hex grids, delete blank rows)
- Hidden sheet-based activity tracking (writes to `_pb_activity` sheet)
- Admin debug tools
- ~400 lines of JavaScript
- No user authorization required (simple triggers can write to sheets)
- Reference source: `scripts/puzzle_tools_addon_latest.gs`

## Deployment

### Automatic Deployment (New Puzzles)

When a new puzzle sheet is created via `addpuzzle.php` or the API, Puzzleboss automatically:

1. **Creates the sheet** via Drive/Sheets API
2. **Deploys the add-on** via `activate_puzzle_sheet_via_api()`:
   - Creates a container-bound Apps Script project
   - Pushes the code from `APPS_SCRIPT_ADDON_CODE` config
   - Initializes spreadsheet metadata
3. **Registers the puzzle** in the database

### Manual Deployment (Existing Sheets)

To deploy/update the add-on on existing sheets:

```bash
# Deploy to a specific puzzle (by ID or name pattern)
curl -X POST "http://localhost:5000/puzzles/activate-addons" \
  -H "Content-Type: application/json" \
  -d '{"puzzle_ids": [123, 456]}'

# Deploy to all puzzles missing the add-on
curl -X POST "http://localhost:5000/puzzles/activate-addons" \
  -H "Content-Type: application/json" \
  -d '{"filter": "missing_addon"}'
```

### Updating the Add-on Code

To change the add-on code deployed to new sheets:

```bash
# Method 1: Direct database update
mysql -u puzzleboss -p puzzleboss << EOF
UPDATE config SET val = '$(cat /path/to/new_code.gs | sed "s/'/''/g")'
WHERE \`key\` = 'APPS_SCRIPT_ADDON_CODE';
EOF

# Method 2: Via pbtools.php UI
# Go to pbtools.php → Config Editor → Edit APPS_SCRIPT_ADDON_CODE
```

**Important**: Updating the config only affects **new puzzle sheets**. Existing sheets retain their deployed version unless manually re-deployed.

## Requirements

### Service Account Setup

The Apps Script API deployment requires:

1. **Domain-Wide Delegation** enabled for the service account
2. **Authorized scopes** in Google Workspace Admin Console:
   ```
   https://www.googleapis.com/auth/drive
   https://www.googleapis.com/auth/spreadsheets
   https://www.googleapis.com/auth/script.projects
   ```

3. **Apps Script API enabled** in Google Cloud Console:
   ```
   https://console.cloud.google.com/apis/api/script.googleapis.com
   ```

### Config Values

In `puzzleboss.yaml`:
```yaml
SERVICE_ACCOUNT_FILE: service-account.json
```

In database `config` table:
```sql
INSERT INTO config (`key`, val) VALUES ('SERVICE_ACCOUNT_SUBJECT', 'bigjimmy@importanthuntpoll.org');
```

## How It Works

### Step 1: Create Container-Bound Script

Uses `script.googleapis.com/v1/projects:create` with `parentId` set to the sheet ID:

```python
script_service.projects().create(body={
    "title": "Puzzle Tools",
    "parentId": sheet_id,
}).execute()
```

This creates a script **bound to the spreadsheet**, visible in Extensions → Apps Script.

### Step 2: Push Code

Uses `script.googleapis.com/v1/projects/{scriptId}:updateContent`:

```python
script_service.projects().updateContent(
    scriptId=script_id,
    body={
        "files": [
            {"name": "Code", "type": "SERVER_JS", "source": addon_code},
            {"name": "appsscript", "type": "JSON", "source": manifest},
        ]
    }
).execute()
```

The code includes:
- `onInstall(e)`: Runs when the add-on is first bound to the sheet
- `onOpen(e)`: Creates the "Puzzle Tools" menu
- `onEdit(e)`: Tracks editor activity by writing to hidden `_pb_activity` sheet
- Tool functions: Grid manipulation, formatting, tab creation, hex grids, etc.

### Step 3: Initialize Activity Tracking

Pre-creates a hidden `_pb_activity` sheet via Sheets API:
- Hidden from the UI
- Warning-protected (users see a warning if they try to manually edit)
- Contains headers: `editor`, `timestamp`, `num_sheets`
- The `onEdit` trigger writes one row per editor, updated in place on each edit

## Monitoring

### Bigjimmybot Integration

Bigjimmybot reads activity from the hidden `_pb_activity` sheet:

```python
# Read activity from hidden sheet
info = get_puzzle_sheet_info_activity(sheet_id)
# Returns: {"editors": [{solvername, timestamp}, ...], "sheetcount": N}

# Falls back to legacy Revisions API for old sheets without add-on
info = get_puzzle_sheet_info_legacy(sheet_id)
# Slow, high quota usage, fallback only for pre-add-on sheets
```

### Metrics

Track add-on deployment via:
- Puzzle database: Check `drive_id` is not NULL
- Developer metadata: Query for `PB_SPREADSHEET` keys
- Logs: Search for "Apps Script API activation complete"

## Troubleshooting

### Add-on Not Appearing in Menu

**Symptoms**: New puzzle sheet created but "Puzzle Tools" menu doesn't appear

**Causes**:
1. Script deployment failed (check logs for errors)
2. Apps Script API not enabled in GCP
3. Service account lacks `script.projects` scope in DWD
4. User hasn't triggered `onOpen` (reload the sheet)

**Fix**:
```bash
# Check logs for activation errors
grep "activate_puzzle_sheet_via_api" /var/log/puzzleboss/pbrest.log

# Manually deploy to the sheet
curl -X POST "http://localhost:5000/puzzles/{puzzle_id}/activate-addon"
```

### Activity Tracking Not Working

**Symptoms**: Puzzle sheet has add-on but bigjimmybot doesn't detect activity

**Causes**:
1. `_pb_activity` sheet not being written to (check with admin if they have access)
2. User email not extractable (runs as "unknown")
3. Bigjimmybot using wrong tracking method (legacy Revisions API instead of hidden sheet)

**Fix**:
```bash
# Check if hidden _pb_activity sheet exists and has data
# Use service account to read the sheet:
# Sheets API: spreadsheets.values.get(spreadsheetId, range="_pb_activity!A:C")
```

### Deployment Fails with 429 Rate Limit

**Symptoms**: Many sheets created at once, some fail activation

**Solution**: The system has built-in retry logic with exponential backoff. Failed sheets will retry automatically. Configure retry behavior:

```sql
-- Increase max retries (default: 10)
INSERT INTO config (`key`, val) VALUES ('BIGJIMMY_QUOTAFAIL_MAX_RETRIES', '20');

-- Increase retry delay (default: 5 seconds)
INSERT INTO config (`key`, val) VALUES ('BIGJIMMY_QUOTAFAIL_DELAY', '10');
```

### Script Code Too Large

**Symptoms**: Import fails with "Data too long for column 'val'"

**Solution**: Expand the `config.val` column to MEDIUMTEXT (16MB) if needed:

```sql
-- Expand column to support large add-on code
ALTER TABLE config MODIFY COLUMN val MEDIUMTEXT DEFAULT NULL;

-- Verify column size
SHOW CREATE TABLE config;
-- Should show: `val` MEDIUMTEXT DEFAULT NULL
```

## Migration from Cookie-Based System

The old cookie-based `/scripts/invoke` system has been **completely removed**. Key differences:

| Feature | Cookie-Based (DEPRECATED) | Apps Script API (CURRENT) |
|---------|--------------------------|---------------------------|
| **Method** | POST to `/scripts/invoke` with browser cookies | Apps Script API with service account |
| **Code Source** | Published add-on (external) | Configurable, stored in database |
| **Credentials** | Browser session cookies (expire frequently) | Service account with DWD (stable) |
| **Updates** | Requires cookie refresh via pbtools.php | Edit config and re-deploy |
| **Maintenance** | High (cookie rotation, health checks) | Low (API-based, no session management) |
| **Function** | `activate_puzzle_sheet_extension()` ❌ DELETED | `activate_puzzle_sheet_via_api()` |

### What Was Removed

The following have been deleted from the codebase:
- ❌ `activate_puzzle_sheet_extension()` in pbgooglelib.py
- ❌ `check_addon_invoke_health()` in pbgooglelib.py
- ❌ `rotate_addon_cookies()` in pbgooglelib.py and bigjimmybot.py
- ❌ `_build_invoke_url()` in pbgooglelib.py
- ❌ `scripts/build_addon_config.py`
- ❌ `scripts/test_cookie_auth.py`
- ❌ `scripts/extract_addon_code.py`
- ❌ `scripts/import_puzzle_tools.py`
- ❌ `scripts/migrate_expand_config_val.sql`

The following config values are now obsolete and can be removed from the database:
- ⚠️ `SHEETS_ADDON_COOKIES`
- ⚠️ `SHEETS_ADDON_INVOKE_PARAMS`


## Reference

### Key Files

| File | Purpose |
|------|---------|
| `pbgooglelib.py` | Core library with `activate_puzzle_sheet_via_api()` and `get_puzzle_sheet_info_activity()` |
| `pbrest.py` | REST API endpoints, calls activation during puzzle creation |
| `scripts/puzzle_tools_addon_latest.gs` | Reference copy of puzzle tools add-on code |
| `scripts/test_apps_script_api.py` | Test script for end-to-end Apps Script API deployment |

### API Endpoints

- `POST /puzzles` - Create puzzle, automatically deploys add-on
- `POST /puzzles/{id}/activate-addon` - Manually deploy to specific puzzle
- `POST /puzzles/activate-addons` - Batch deploy to multiple puzzles

### Configuration Keys

```sql
-- View current add-on config
SELECT `key`, LENGTH(val) as size_bytes FROM config
WHERE `key` LIKE 'APPS_SCRIPT%';

-- Update add-on code (be careful with escaping!)
UPDATE config SET val = '<new_code>' WHERE `key` = 'APPS_SCRIPT_ADDON_CODE';
```

## Future Enhancements

- **Version control**: Track add-on code versions, allow rollback
- **A/B testing**: Deploy different add-on versions to different puzzles
- **Auto-update**: Periodically re-deploy add-on to existing sheets
- **Custom triggers**: Deploy time-based or onChange triggers (requires auth)
