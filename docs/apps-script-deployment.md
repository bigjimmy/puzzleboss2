# Apps Script Deployment System

## Overview

Puzzleboss deploys a customizable Apps Script add-on to puzzle sheets using the **Google Apps Script API**. This replaces the previous cookie-based `/scripts/invoke` method with a more maintainable, API-driven approach.

The deployed add-on provides:
- **Puzzle Tools**: Grid manipulation (symmetry, crossword formatting, hex grids, etc.)
- **Activity Tracking**: Records solver activity via DeveloperMetadata for bigjimmybot

## Architecture

```
Puzzle Creation Flow (NEW):
  addpuzzle.php (UI)  →  pbrest.py  →  pbgooglelib.activate_puzzle_sheet_via_api()
                                        ├── Creates container-bound Apps Script project
                                        ├── Deploys code from APPS_SCRIPT_ADDON_CODE config
                                        └── Initializes PB_SPREADSHEET metadata

Activity Tracking Flow:
  User edits cell  →  Apps Script onEdit trigger  →  Writes DeveloperMetadata
                                                      (PB_ACTIVITY:username, PB_SHEET)
  bigjimmybot.py   →  Sheets API DeveloperMetadata.search()  →  Updates puzzle DB
```

## Configuration

### Database Config Values

| Key | Description | Default |
|-----|-------------|---------|
| `APPS_SCRIPT_ADDON_CODE` | The Apps Script code to deploy (JavaScript) | Falls back to simple onEdit tracker |
| `APPS_SCRIPT_ADDON_MANIFEST` | The appsscript.json manifest | Default V8 runtime config |

### Current Add-on Code

The current deployed code is from **dannybd/sheets-puzzleboss-tools** which combines:
- Puzzle-solving utilities (symmetry, formatting, tab creation)
- DeveloperMetadata-based activity tracking
- Admin debug tools

Source: `scripts/puzzle_tools_addon_latest.gs`

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
# Method 1: Import from a local file
docker exec puzzleboss-app python3 /app/scripts/import_puzzle_tools.py \
  --from-file /path/to/new_code.gs

# Method 2: Import from an Apps Script project (requires DWD impersonation)
docker exec puzzleboss-app python3 /app/scripts/import_puzzle_tools.py \
  --script-id <APPS_SCRIPT_PROJECT_ID>

# Method 3: Update directly in database (via admin UI or SQL)
# Edit the APPS_SCRIPT_ADDON_CODE config value
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
- `onEdit(e)`: Tracks editor activity via DeveloperMetadata
- Tool functions: Grid manipulation, formatting, etc.

### Step 3: Initialize Metadata

The add-on's `updateSpreadsheetStats()` function (called from `onOpen`) creates:

```javascript
{
  key: "PB_SPREADSHEET",
  value: '{"t": 1766285432, "num_sheets": 3}'
}
```

This metadata signals to bigjimmybot that the sheet is ready for DeveloperMetadata-based tracking (instead of the legacy Revisions API).

## Monitoring

### Bigjimmybot Integration

Bigjimmybot automatically detects sheets with DeveloperMetadata and uses the efficient tracking method:

```python
# Check if sheet has PB metadata
has_metadata = check_developer_metadata_exists(sheet_id)

if has_metadata:
    # Use fast DeveloperMetadata API
    info = get_puzzle_sheet_info(sheet_id)
else:
    # Fall back to slow Revisions API
    info = get_puzzle_sheet_info_legacy(sheet_id)
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
1. DeveloperMetadata not being written (check with admin debug menu)
2. Bigjimmybot using legacy Revisions API instead
3. User email not extractable (runs as "unknown")

**Fix**:
```python
# Test metadata detection
check_developer_metadata_exists(sheet_id)  # Should return True

# Force bigjimmybot to check again
# (it auto-upgrades sheets when it detects PB_SPREADSHEET metadata)
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

**Solution**: The migration script `migrate_expand_config_val.sql` expands the column to MEDIUMTEXT (16MB). If already run and still failing, the script may exceed 16MB (unlikely for reasonable add-on code).

## Migration from Cookie-Based System

The old cookie-based `/scripts/invoke` system is **deprecated** but still present in the codebase. Key differences:

| Feature | Cookie-Based (OLD) | Apps Script API (NEW) |
|---------|-------------------|----------------------|
| **Method** | POST to `/scripts/invoke` with browser cookies | Apps Script API with service account |
| **Code Source** | Published add-on (external) | Configurable, stored in database |
| **Credentials** | Browser session cookies (expire frequently) | Service account with DWD (stable) |
| **Updates** | Requires cookie refresh via pbtools.php | Edit config and re-deploy |
| **Maintenance** | High (cookie rotation, health checks) | Low (API-based, no session management) |
| **Function** | `activate_puzzle_sheet_extension()` | `activate_puzzle_sheet_via_api()` |

### Old System Cleanup

The following can be removed once migration is complete:
- `activate_puzzle_sheet_extension()` in pbgooglelib.py
- `check_addon_invoke_health()` in pbgooglelib.py
- `rotate_addon_cookies()` in pbgooglelib.py and bigjimmybot.py
- `SHEETS_ADDON_COOKIES` and `SHEETS_ADDON_INVOKE_PARAMS` config values
- pbtools.php form for cookie/invoke URL capture
- docs/google-sheets-addon.md sections on cookie management

## Reference

### Key Files

| File | Purpose |
|------|---------|
| `pbgooglelib.py` | Core library with `activate_puzzle_sheet_via_api()` |
| `pbrest.py` | REST API endpoints, calls activation during puzzle creation |
| `scripts/puzzle_tools_addon_latest.gs` | Reference copy of current add-on code |
| `scripts/import_puzzle_tools.py` | Import tool for updating add-on code |
| `scripts/migrate_expand_config_val.sql` | DB migration to support large code |

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
