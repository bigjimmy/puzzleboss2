# Google Sheets Add-on: Activity Tracking Extension

## Overview

Puzzleboss uses a Google Sheets add-on (Apps Script extension) bound to puzzle spreadsheets to track solver activity. When a solver edits a cell, the extension writes `DeveloperMetadata` to the sheet with:

- `PB_ACTIVITY:<username>` — which user edited and when
- `PB_SPREADSHEET` — marks the sheet as having the extension active

`bigjimmybot.py` reads this metadata via the Sheets API to update puzzle activity in the database (`lastsheetact`, `sheetcount`). This approach is significantly more quota-efficient than the legacy Revisions API fallback.

## Architecture

```
Puzzle Creation Flow:
  addpuzzle.php (UI)  →  pbrest.py (Step 3)  →  pbgooglelib.py
                                                    ├── create_puzzle_sheet()
                                                    └── activate_puzzle_sheet_extension()
                                                         └── POST /scripts/invoke (Google internal)

Activity Tracking Flow:
  User edits cell  →  Apps Script onEdit trigger  →  Writes DeveloperMetadata
  bigjimmybot.py   →  Sheets API DeveloperMetadata.search()  →  Updates puzzle DB
```

### Key Functions

| Function | File | Purpose |
|----------|------|---------|
| `activate_puzzle_sheet_extension()` | `pbgooglelib.py:899` | Activates add-on on a sheet via `/scripts/invoke` |
| `check_addon_invoke_health()` | `pbgooglelib.py:1017` | Tests if invoke credentials are still valid (returns 1/0) |
| `rotate_addon_cookies()` | `pbgooglelib.py:1082` | Auto-rotates `__Secure-1PSIDTS` / `__Secure-3PSIDTS` cookies |
| `get_puzzle_sheet_info()` | `pbgooglelib.py` | Reads activity via DeveloperMetadata API (new approach) |
| `get_puzzle_sheet_info_legacy()` | `pbgooglelib.py` | Reads activity via Revisions API (fallback) |

### Hybrid Tracking Approach

The `puzzle.sheetenabled` column controls which tracking method bigjimmybot uses:

- `sheetenabled=1` — Use DeveloperMetadata API (fast, low quota)
- `sheetenabled=0` — Use legacy Revisions API (slow, high quota), auto-upgrade when metadata detected

## Configuration

Two config entries in the database `config` table are required:

### `SHEETS_ADDON_COOKIES`

JSON object containing Google session cookies from `docs.google.com`. These are extracted from a browser session.

**Minimum required cookies:** `SID`, `OSID`, `__Secure-1PSID`, `__Secure-1PSIDTS`

The `__Secure-1PSIDTS` (and `__Secure-3PSIDTS`) cookies rotate automatically via Google's `RotateCookies` endpoint — bigjimmybot handles this every 50 loops. The core session cookies (`SID`, `OSID`, `__Secure-1PSID`) are longer-lived but will eventually expire (typically days to weeks).

Example:
```json
{
  "SID": "g.a000...",
  "OSID": "g.a000...",
  "__Secure-1PSID": "g.a000...",
  "__Secure-1PSIDTS": "sidts-CjIB...",
  "__Secure-3PSIDTS": "sidts-CjIB..."
}
```

### `SHEETS_ADDON_INVOKE_PARAMS`

JSON object containing the full query string from a `/scripts/invoke` request captured in browser DevTools. The full query string is stored (not individual parameters) because Google's add-on framework uses many undocumented parameters (`includes_info_params`, `ctx`, `eei`, `ruid`, etc.) that are required for the add-on to fully activate and create installable triggers.

At invocation time, the `id=` parameter is replaced with the target sheet ID.

Example:
```json
{
  "query_string": "id=SHEET_ID&sid=1f48544a74c53eaf&vc=1&c=1&w=1&flr=0&smv=2147483647&smb=%5B2147483647%2C%20APwL%5D&ruid=52&lib=MGbbKKh6PzO7n4XKLGDRZxVVT43b8S2kx&func=populateMenus&ctx=...&eei=...&did=AKfycbw2OFUmjSGozHe6i_G0_biODAk6NOzIfHkwoaKKzSGORZ0&token=AC4w5Vg-...&ouid=112391333398687811083&includes_info_params=true&cros_files=false&nded=false"
}
```

Key parameters within the query string:

| Param | Description | Stability |
|-------|-------------|-----------|
| `sid` | Session identifier (hex string) | Changes with browser session |
| `token` | Auth token (contains embedded timestamp) | Changes with browser session |
| `lib` | Apps Script library/project ID | Stable (tied to the add-on) |
| `did` | Deployment ID | Stable (tied to the add-on deployment) |
| `ouid` | Google account numeric ID | Stable (tied to the Google account) |
| `includes_info_params` | Required for full activation | Always `true` |
| `ruid`, `vc`, `c`, `w`, `flr`, `smv`, `smb` | Internal Google params | Varies |

**Note:** A legacy format with individual keys (`sid`, `token`, `lib`, `did`, `ouid`) is still supported for backward compatibility but may not fully activate the extension. The `query_string` format is strongly preferred.

## Credential Refresh

### When to Refresh

Credentials need refreshing when:
- The `addon_invoke_healthy` botstats metric drops to `0`
- bigjimmybot logs severity-1: "Add-on invoke health check FAILED"
- New puzzles fail activation (401 errors in logs)
- Grafana alerts on the metric (if configured)

### How to Refresh (pbtools UI)

The easiest method is the form on the **Puzzleboss-only Admin Tools** page (`pbtools.php`):

1. Open any puzzle sheet that has the PB add-on active in Chrome
2. Open DevTools (F12) → **Network** tab
3. In the filter box, type `scripts/invoke`
4. Trigger the add-on: click **Extensions → Mystery Hunt Tools → Enable for this spreadsheet**
5. Click the `invoke` request in the Network tab
6. From the **Headers** tab:
   - **Cookie:** Right-click the Cookie header value → "Copy value"
   - **Request URL:** Right-click the URL → "Copy link address" (the **full** URL with all query params)
7. Paste both into the form on `pbtools.php` and submit

**Important:** The full invoke URL must be preserved — it contains many undocumented Google parameters (`includes_info_params`, `ctx`, `eei`, `ruid`, etc.) that are required for the add-on to fully activate and create installable triggers. The form stores the entire query string.

### How to Refresh (CLI)

```bash
# Parse raw browser data and output config JSON
python3 scripts/build_addon_config.py \
  --raw-cookies "COMPASS=...; SID=...; ..." \
  --invoke-url "https://docs.google.com/.../scripts/invoke?id=...&sid=...&token=..."

# Test credentials against a live sheet
python3 scripts/test_cookie_auth.py \
  --raw-cookies "..." \
  --invoke-url "..."

# Test credentials already saved in config DB (run on server)
python3 scripts/test_cookie_auth.py
```

## Monitoring

### bigjimmybot Health Check

Every 10 main loops, bigjimmybot:
1. Picks a puzzle sheet with `sheetenabled=1`
2. Calls `check_addon_invoke_health(sheet_id)`
3. Posts the result as `addon_invoke_healthy` (1 or 0) to `/botstats/addon_invoke_healthy`
4. Logs severity-1 if the health check fails

### Grafana / Prometheus

Query the botstats API endpoint to get the metric:
```
GET /botstats  →  { "addon_invoke_healthy": "1", ... }
```

Set up a Grafana alert when `addon_invoke_healthy` is `0` for more than one check cycle.

## Troubleshooting

### Activation returns 401

Cookies have expired. Refresh via pbtools.php (see above).

### Activation returns 400

The invoke URL params are wrong. Usually means `lib` or `did` are missing or incorrect. Re-capture from DevTools.

### Activation returns 200 but sheet doesn't track activity

The add-on activated (`populateMenus` ran), but the installable `onEdit` trigger may not have been created. This can happen if:
- The add-on code itself has an issue
- The sheet doesn't have the right permissions

Check bigjimmybot logs — if it detects `PB_SPREADSHEET` metadata, it will auto-set `sheetenabled=1`.

### Cookies work for invoke but not page loads

This is expected behavior. The cookies authenticate RPC calls to `/scripts/invoke` but do NOT work for loading regular pages (`/edit`, `/export`, Google homepage). This means we cannot auto-refresh `sid`/`token` by scraping sheet pages.

### 2SV (Two-Step Verification) prompt on sheets

If users see "To protect your account, you need to turn on 2-Step Verification", this is a Google Workspace admin policy issue — NOT caused by the add-on. Check:
- Google Workspace Admin Console → Security → Authentication → 2-Step Verification
- Child organizational unit overrides
- Configuration group policies

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `scripts/build_addon_config.py` | Parse raw browser data → config JSON |
| `scripts/test_cookie_auth.py` | Test cookie auth + invoke endpoint |
| `scripts/test_apps_script_api.py` | Test Apps Script API with service account (for future approach) |

## Future Work

### 1. Build a Maintainable Apps Script Add-on

**Priority: Medium | Effort: Medium**

The current add-on is a third-party extension bound to a template sheet. The long-term plan is to create a new add-on owned by the team's Google Workspace account and defined in this repository. This would:

- Eliminate dependency on browser cookie harvesting
- Use the official Apps Script Execution API with the existing service account
- Allow code updates without manual sheet editing
- Be deployable via `clasp` (Apps Script CLI)

### 2. Remove Duplicate Legacy Puzzle Creation Code

**Priority: Low | Effort: Low**

The old one-step puzzle creation endpoint in `pbrest.py` is still present alongside the new stepwise creation flow. The legacy code should be removed or refactored into a wrapper around the stepwise flow to reduce maintenance burden.

### 3. Fix deploy.sh Error Handling

**Priority: Low | Effort: Low**

`deploy.sh` currently stops if one post-deploy restart fails (e.g., if bigjimmybot isn't running). It should continue with remaining restarts and report all failures at the end.
