# Google Sheets Add-on: Activity Tracking and Puzzle Tools

## Overview

Puzzleboss deploys a configurable Apps Script add-on to puzzle spreadsheets via the **Apps Script API**. This add-on provides:

1. **Activity Tracking**: Records solver edits via `DeveloperMetadata` for bigjimmybot
2. **Puzzle Tools** (optional): Grid manipulation, crossword formatting, tab creation (from [dannybd/sheets-puzzleboss-tools](https://github.com/dannybd/sheets-puzzleboss-tools))

The add-on is deployed automatically when new puzzles are created, using a **service account with Domain-Wide Delegation** — no browser cookies or manual activation required.

## Architecture

```
Puzzle Creation Flow (Apps Script API):
  addpuzzle.php (UI)  →  pbrest.py (Step 3)  →  pbgooglelib.py
                                                   ├── create_puzzle_sheet()
                                                   └── activate_puzzle_sheet_via_api()
                                                        ├── Apps Script API: projects.create
                                                        ├── Apps Script API: projects.updateContent
                                                        └── (Optional) Create hidden _pb_activity sheet

Activity Tracking Flow (Default Minimal Tracker):
  User edits cell  →  Apps Script onEdit trigger  →  Writes to hidden _pb_activity sheet
                                                      (email, timestamp, num_sheets)
  bigjimmybot.py   →  Sheets API values.get()  →  Updates puzzle DB

Activity Tracking Flow (Full Puzzle Tools):
  User edits cell  →  Apps Script onEdit trigger  →  Writes DeveloperMetadata
                                                      (PB_ACTIVITY:username, PB_SPREADSHEET, PB_SHEET)
  bigjimmybot.py   →  Sheets API DeveloperMetadata.search()  →  Updates puzzle DB
```

### Key Differences from Legacy Cookie-Based System

|  | **Cookie-Based (DEPRECATED)** | **Apps Script API (CURRENT)** |
|---|---------------------------|---------------------------|
| **Authentication** | Browser session cookies (SID, __Secure-1PSID, etc.) | Service account with Domain-Wide Delegation |
| **Activation** | POST to `/scripts/invoke` endpoint | Apps Script API (`projects.create` + `updateContent`) |
| **Code Source** | External add-on (hardcoded) | Configurable via `APPS_SCRIPT_ADDON_CODE` |
| **Maintenance** | Cookie rotation every 50 loops, health checks | None — API uses stable service account credentials |
| **Reliability** | Cookies expire unpredictably (401 errors) | Service account credentials do not expire |

**The cookie-based system has been removed as of this branch.**

## Configuration

### Required: Service Account Setup

The Apps Script API deployment requires:

1. **Service Account** with Domain-Wide Delegation enabled
2. **Authorized Scopes** in Google Workspace Admin Console:
   ```
   https://www.googleapis.com/auth/drive
   https://www.googleapis.com/auth/spreadsheets
   https://www.googleapis.com/auth/script.projects
   ```
3. **Apps Script API Enabled** in Google Cloud Console:
   ```
   https://console.cloud.google.com/apis/api/script.googleapis.com
   ```

### Config Values

#### Database (`config` table)

| Key | Description | Default |
|-----|-------------|---------|
| `APPS_SCRIPT_ADDON_CODE` | Apps Script code to deploy (JavaScript) | Falls back to simple onEdit tracker |
| `APPS_SCRIPT_ADDON_MANIFEST` | The appsscript.json manifest | Default V8 runtime config |
| `SERVICE_ACCOUNT_FILE` | Path to service account JSON key | `service-account.json` |
| `SERVICE_ACCOUNT_SUBJECT` | Domain admin email for impersonation | *(must be set)* |

#### Static (`puzzleboss.yaml`)

```yaml
SERVICE_ACCOUNT_FILE: service-account.json
```

### Add-on Code Options

**Option 1: Default Activity Tracker (Minimal)**
- Leave `APPS_SCRIPT_ADDON_CODE` empty or unset
- Deploys a simple `onEdit` trigger that writes to a hidden `_pb_activity` sheet
- ~85 lines of JavaScript
- No UI, no puzzle tools — just activity tracking
- **Tracking method**: Hidden `_pb_activity` sheet (no authorization required)
- **Why this approach?** Simple triggers can write to sheets without authorization, but DeveloperMetadata operations require authorized access

**Option 2: Full Puzzle Tools (Recommended)**
- Set `APPS_SCRIPT_ADDON_CODE` to the content of `scripts/puzzle_tools_addon_latest.gs`
- Includes activity tracking PLUS:
  - 🔠 Resize Cells into Squares
  - 🪞 Symmetrify Grid (rotational/bilateral)
  - 🗂️ Quick-Add Named Tabs
  - 📰 Format as Crossword Grid
  - 🐝 Add Hexagonal Grid Sheet
  - 🫥 Delete Blank Rows
- ~400 lines of JavaScript
- Based on [dannybd/sheets-puzzleboss-tools](https://github.com/dannybd/sheets-puzzleboss-tools)
- **Tracking method**: DeveloperMetadata API (requires menu authorization, but faster and cleaner)

To deploy the full puzzle tools, run the production migration SQL:
```bash
mysql -u puzzleboss -p puzzleboss < PRODUCTION_MIGRATION.sql
```

## Deployment

### Automatic (New Puzzles)

When a new puzzle is created via `addpuzzle.php` or the API:
1. Sheet is created via Sheets API
2. **Apps Script add-on is deployed automatically** via `activate_puzzle_sheet_via_api()`
3. Puzzle is registered in the database

No manual action required!

### Manual (Existing Puzzles)

To deploy/update the add-on on existing sheets without it:

```bash
# Deploy to a specific puzzle by ID
curl -X POST "http://localhost:5000/puzzles/123/activate-addon"

# Deploy to multiple puzzles
curl -X POST "http://localhost:5000/puzzles/activate-addons" \
  -H "Content-Type: application/json" \
  -d '{"puzzle_ids": [123, 456, 789]}'

# Deploy to all unsolved puzzles missing the add-on
curl -X POST "http://localhost:5000/puzzles/activate-addons" \
  -H "Content-Type: application/json" \
  -d '{"filter": "missing_addon"}'
```

**Note:** Re-deploying the add-on to a sheet that already has one will create a second Apps Script project. This is harmless but creates clutter. The `/activate-addons` endpoint is primarily for migrating old sheets.

## Activity Tracking

### Hidden Sheet Approach

The default add-on writes activity data to a hidden `_pb_activity` sheet that bigjimmybot reads:

| Column | Value | Purpose |
|--------|-------|---------|
| `editor` | `alice@example.org` | Full email address of the editor |
| `timestamp` | `1766285432` | Unix timestamp of last edit |
| `num_sheets` | `5` | Number of sheets in the spreadsheet (excluding _pb_activity) |

**Why a hidden sheet instead of DeveloperMetadata?**

Simple triggers (like `onEdit`) can write to sheets without requiring user authorization, but DeveloperMetadata operations require authorized access. Using a hidden sheet allows activity tracking to work without any user authorization prompts.

The sheet is:
- Pre-created by the service account during deployment
- Hidden from the UI (not visible in the sheet tab list)
- Warning-protected (users see a warning if they try to manually edit it)
- One row per editor (updated in-place on each edit)

### Tracking Method Selection

Bigjimmybot uses different methods to read activity depending on the sheet:

1. **Hidden Sheet (_pb_activity)** — Default for new sheets with Apps Script add-on
   - Fast, low quota usage
   - Reads via `get_puzzle_sheet_info_activity()`
   - No special configuration needed

2. **DeveloperMetadata** — Used by full puzzle tools add-on only
   - Fast, low quota usage
   - Reads via `get_puzzle_sheet_info()`
   - Only available with the full puzzle tools (not the minimal tracker)

3. **Revisions API (Legacy)** — Fallback for old sheets without add-on
   - Slow, high quota usage
   - Reads via `get_puzzle_sheet_info_legacy()`
   - Used for sheets that don't have the add-on deployed

Bigjimmybot automatically detects which method to use based on sheet configuration.

## Updating Add-on Code

To change the code deployed to **new** sheets during a hunt:

### Method 1: Direct Database Update (Quick)

```sql
-- Update the code
UPDATE config SET val = '<new_javascript_code>' WHERE `key` = 'APPS_SCRIPT_ADDON_CODE';
```

### Method 2: Import from File

```bash
# Create a file with your new code
cat > /tmp/new_addon.gs << 'EOF'
function onEdit(e) {
  // Your new code here
}
EOF

# Import via SQL
mysql -u puzzleboss -p puzzleboss << EOF
UPDATE config SET val = '$(cat /tmp/new_addon.gs | sed "s/'/''/g")'
WHERE \`key\` = 'APPS_SCRIPT_ADDON_CODE';
EOF
```

### Method 3: Via pbtools.php UI

1. Go to `pbtools.php` → **Config Editor**
2. Find `APPS_SCRIPT_ADDON_CODE`
3. Paste new code
4. Save

**Important:** Updating the config only affects **new** puzzle sheets created after the change. Existing sheets retain their deployed version. To update existing sheets, use the manual deployment endpoint.

## Monitoring

### Key Functions

| Function | File | Purpose |
|----------|------|---------|
| `activate_puzzle_sheet_via_api()` | `pbgooglelib.py` | Deploys add-on via Apps Script API |
| `get_puzzle_sheet_info_activity()` | `pbgooglelib.py` | Reads activity from hidden _pb_activity sheet (default tracker) |
| `get_puzzle_sheet_info()` | `pbgooglelib.py` | Reads activity via DeveloperMetadata API (full puzzle tools) |
| `get_puzzle_sheet_info_legacy()` | `pbgooglelib.py` | Reads activity via Revisions API (fallback for old sheets) |
| `check_developer_metadata_exists()` | `pbgooglelib.py` | Quick check if sheet has PB DeveloperMetadata (full puzzle tools only) |

### Logs

Search for these patterns in `pbrest.log`:

```bash
# Successful activations
grep "Apps Script API activation complete" pbrest.log

# Activation failures
grep "Apps Script activation failed" pbrest.log | grep -v "non-fatal"

# Quota issues
grep "Rate limit creating script" pbrest.log
```

### Prometheus Metrics

If `prometheus_flask_exporter` is installed:
- **Removed:** `addon_invoke_healthy` metric (was for cookie system)
- Monitor API failures via general request metrics

## Troubleshooting

### Add-on Not Appearing in Menu

**Symptoms:** New puzzle sheet created but "Puzzle Tools" menu doesn't appear

**Causes:**
1. Script deployment failed → Check logs: `grep "activate_puzzle_sheet_via_api" pbrest.log`
2. Apps Script API not enabled in GCP
3. Service account lacks `script.projects` scope in Domain-Wide Delegation
4. User hasn't triggered `onOpen` → Reload the sheet

**Fix:**
```bash
# Manually deploy to the sheet
curl -X POST "http://localhost:5000/puzzles/{puzzle_id}/activate-addon"
```

### Activity Tracking Not Working

**Symptoms:** Puzzle sheet has add-on but bigjimmybot doesn't detect activity

**Causes:**
1. DeveloperMetadata not being written → Check with admin debug menu (if admin)
2. Bigjimmybot using legacy Revisions API → Check `puzzle.sheetenabled` column
3. User email not extractable → Runs as "unknown"

**Fix:**
```python
# Test metadata detection
from pbgooglelib import check_developer_metadata_exists
check_developer_metadata_exists(sheet_id)  # Should return True
```

### Deployment Fails with 403 Permission Denied

**Symptoms:** `activate_puzzle_sheet_via_api` returns False, logs show "Insufficient Permission"

**Causes:**
1. Apps Script API not enabled in Google Cloud Console
2. Service account lacks Domain-Wide Delegation
3. `script.projects` scope not authorized

**Fix:**
1. Enable API: https://console.cloud.google.com/apis/api/script.googleapis.com
2. Verify DWD scopes in Admin Console: Security → API controls → Domain-wide delegation
3. Ensure `https://www.googleapis.com/auth/script.projects` is included

### Deployment Fails with 429 Rate Limit

**Symptoms:** Many sheets created at once, some fail with rate limit errors

**Solution:** The system has built-in retry logic with exponential backoff. Failed sheets will retry automatically. Configure behavior:

```sql
-- Increase max retries (default: 10)
UPDATE config SET val = '20' WHERE `key` = 'BIGJIMMY_QUOTAFAIL_MAX_RETRIES';

-- Increase retry delay (default: 5 seconds)
UPDATE config SET val = '10' WHERE `key` = 'BIGJIMMY_QUOTAFAIL_DELAY';
```

## Scripts Reference

| Script | Purpose | Status |
|--------|---------|--------|
| `scripts/test_apps_script_api.py` | Test Apps Script API deployment end-to-end | ✅ Active |
| `scripts/puzzle_tools_addon_latest.gs` | Reference copy of full puzzle tools code | ✅ Active |
| `scripts/puzzle_tools_addon.gs` | Earlier version (Jason's original extraction) | ⚠️ Reference only |

## Related Documentation

- **[docs/apps-script-deployment.md](apps-script-deployment.md)** — Comprehensive guide to the deployment system
- **[dannybd/sheets-puzzleboss-tools](https://github.com/dannybd/sheets-puzzleboss-tools)** — Upstream puzzle tools repository

## Migration from Cookie-Based System

**Status:** The cookie-based activation system has been completely removed.

**If you have old documentation or scripts referencing:**
- `activate_puzzle_sheet_extension()` ❌ Deleted
- `check_addon_invoke_health()` ❌ Deleted
- `rotate_addon_cookies()` ❌ Deleted
- `_build_invoke_url()` ❌ Deleted
- `SHEETS_ADDON_COOKIES` config ⚠️ Deprecated (can be removed from DB)
- `SHEETS_ADDON_INVOKE_PARAMS` config ⚠️ Deprecated (can be removed from DB)
- `scripts/build_addon_config.py` ❌ Deleted
- `scripts/test_cookie_auth.py` ❌ Deleted

**These have all been replaced by `activate_puzzle_sheet_via_api()` and the Apps Script API.**
