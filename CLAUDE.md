# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Puzzleboss 2000 is a puzzle hunt management system developed by ATTORNEY for mystery hunt teams. It provides a REST API backend (Python/Flask), web UI (PHP/JavaScript/Vue.js), Google Sheets integration, Discord bot integration, and an AI assistant bot (BigJimmy) for tracking solver activity.

## Architecture

### Core Components

**Backend (Python)**
- `pbrest.py` - Flask REST API server with MySQL database. Main entry point for API operations. Uses Flasgger for Swagger/OpenAPI documentation.
- `pblib.py` - Core library with configuration management, solver assignment/unassignment, activity logging, and email functions. Loads config from both `puzzleboss.yaml` (static) and database `config` table (dynamic). Config auto-refreshes every 30 seconds via `maybe_refresh_config()`. All functions that accept ID parameters normalize to `int()` at the boundary.
- `pbgooglelib.py` - Google Drive/Sheets integration. Uses service account credentials (`service-account.json`) with Domain-Wide Delegation. Creates puzzle sheets, tracks sheet revisions. Supports hybrid metadata approach for sheet activity tracking.
- `pbdiscordlib.py` - Discord integration via socket connection to puzzcord daemon. Creates channels, announces solves/rounds.
- `pbllmlib.py` - LLM-powered natural language queries via Google Gemini. Includes function calling for hunt data and RAG support for wiki content via ChromaDB.
- `bigjimmybot.py` - Multi-threaded bot that polls Google Sheets for activity and updates puzzle metadata (sheetcount, lastsheetact). Uses hybrid approach: reads hidden `_pb_activity` sheet for sheets with add-on, falls back to legacy Revisions API for old sheets.
- `migrations/` - Data migration framework. Each module has `name`, `description`, and `run(conn)`. Discoverable via `GET /migrate`, executable via `POST /migrate/<name>`. Migrations are idempotent and intended to be pruned after they've been run everywhere.

**Frontend (PHP + JavaScript)**
- `www/puzzlebosslib.php` - Shared PHP library for API calls (`readapi`, `postapi`, `deleteapi`), authentication via `REMOTE_USER` header, and error handling.
- `www/index.php` - Main Vue.js-based UI showing rounds and puzzles with real-time updates, filtering, and tagging.
- `www/*.php` - Various UI pages for adding/editing puzzles, rounds, solvers, admin config, etc.
- `www/*.js` - Vue.js components for round display, tag selection, solve sounds.

**Database (MySQL)**
- Schema defined in `scripts/puzzleboss.sql`
- Key tables: `puzzle`, `round`, `solver`, `activity`, `tag`, `puzzle_tag`, `config`, `botstats`, `newuser`, `privs`
- `config` table stores runtime configuration that can be modified via admin UI
- `puzzle.sheetenabled` column indicates if sheet has add-on deployed (hybrid approach)

### Key Integration Points

**Google Sheets Activity Tracking (Hybrid Approach)**
- Old approach: `get_puzzle_sheet_info_legacy()` in pbgooglelib.py uses Revisions API (quota-heavy)
- New approach: `get_puzzle_sheet_info_activity()` reads hidden `_pb_activity` sheet (quota-light)
- bigjimmybot.py checks `puzzle.sheetenabled` column to decide which method to use
- Sheets with Apps Script add-on deployed automatically write activity to hidden `_pb_activity` sheet

**Configuration System**
- Static config: `puzzleboss.yaml` (database credentials, API endpoints, feature flags)
- Dynamic config: `config` table in database (team name, hunt settings, toggles)
- Both loaded in `pblib.py` via `refresh_config()`, stored in global `configstruct` dict
- Periodic refresh every 30 seconds via `maybe_refresh_config()` called on each API request

**Discord Integration**
- Puzzcord daemon listens on socket (host/port in config)
- Commands: `create_json`, `_round`, `_new`, `_solve`, `_attention`, `message`
- Can be disabled via `SKIP_PUZZCORD=true` config flag

**Optional Features**
- Google API: Disable via `SKIP_GOOGLE_API=true` in puzzleboss.yaml
- Memcache: Enable via `MEMCACHE_ENABLED=true` in config table, caches `/allcached` endpoint
- Prometheus metrics: Exposed at `/metrics` endpoint if prometheus_flask_exporter installed
- LLM queries: Requires google-genai SDK, enabled at `/v1/query` endpoint
- Wiki RAG: Requires chromadb, configured via `WIKI_URL` and `WIKI_CHROMADB_PATH` in config table

## Development Setup

### Option 1: Docker (Recommended for Local Development)

The fastest way to get started is with Docker:

```bash
# Build and start all services (MySQL + App)
docker-compose up --build

# Access the application
# Web UI: http://localhost?assumedid=testuser
# API/Swagger: http://localhost:5000/apidocs
# MySQL: localhost:3306 (user: puzzleboss, pass: puzzleboss123)
```

The Docker setup:
- Automatically initializes the database with schema
- Creates a test user (`testuser`) with admin privileges
- Runs Apache (PHP frontend) + Gunicorn (Python API) in one container
- Enables live code reloading via volume mounts
- Disables optional integrations (Google, Discord) by default

See `docker/README.md` for detailed Docker documentation.

### Option 2: Native Installation

For native development without Docker:

```bash
# System requirements
# - Python >= 3.8
# - MySQL server
# - Apache with PHP (for www/ frontend)

# Install Python dependencies
pip install -r requirements.txt

# Database setup
mysql -u puzzleboss -p puzzleboss < scripts/puzzleboss.sql

# Configuration
cp puzzleboss-SAMPLE.yaml puzzleboss.yaml
# Edit puzzleboss.yaml with database credentials and API endpoints
```

### Google Service Account Setup (Optional)
```bash
# 1. Create a service account with Domain-Wide Delegation in Google Cloud Console
# 2. Download the JSON key file and place it in the app directory as service-account.json
# 3. Authorize the service account's client ID in Google Workspace Admin Console
#    (Security → API controls → Domain-wide delegation) with these scopes:
#    https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/drive.file,
#    https://www.googleapis.com/auth/drive.appdata,https://www.googleapis.com/auth/drive.metadata.readonly,
#    https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/admin.directory.user
# 4. Set config values in the database:
#    SERVICE_ACCOUNT_FILE = service-account.json
#    SERVICE_ACCOUNT_SUBJECT = admin@yourdomain.org  (domain admin email to impersonate)
```

### Running Services

**REST API (Development)**
```bash
# Run on localhost:5000
python pbrest.py
```

**REST API (Production)**
```bash
# Use gunicorn with wsgi.py
gunicorn -c gunicorn_config.py wsgi:app
```

**BigJimmy Bot**
```bash
# Runs continuously, polling sheets for activity
python bigjimmybot.py
```

**PHP Frontend (Development)**
```bash
# Simple test server with CORS
cd www
python simple-server-w-cors.py

# Or use PHP built-in server
php -S localhost:8080
```

**Swagger API Documentation**
- Accessible at http://localhost:5000/apidocs when pbrest.py is running
- API specs defined in individual `swag/*.yaml` files

## Testing

**Unit Tests (pytest)**
```bash
# Run all unit tests (can run locally, no Docker needed — uses mocked DB)
python3 -m pytest tests/ -v

# Run specific test file
python3 -m pytest tests/test_pblib_id_types.py -v
```

**IMPORTANT:** API and UI test suites should be run inside the Docker container to ensure consistent dependencies (PyYAML, Playwright, etc.) and clean database state.

**API Integration Tests**
```bash
# Run comprehensive test suite covering all endpoints (ALWAYS USE DOCKER)
docker exec puzzleboss-app python /app/scripts/test_api_coverage.py --allow-destructive

# Run specific API tests by number
docker exec puzzleboss-app python /app/scripts/test_api_coverage.py --allow-destructive --tests 1 5 10

# List available API tests
docker exec puzzleboss-app python /app/scripts/test_api_coverage.py --list

# Test solver assignment logic
docker exec puzzleboss-app python /app/scripts/test_solver_assignments.py
```

**UI Tests (Playwright)**
```bash
# Run all comprehensive UI tests (ALWAYS USE DOCKER)
docker exec puzzleboss-app python /app/scripts/test_ui_comprehensive.py --allow-destructive

# Run specific UI tests by number
docker exec puzzleboss-app python /app/scripts/test_ui_comprehensive.py --allow-destructive --tests 1 5 10

# List available UI tests
docker exec puzzleboss-app python /app/scripts/test_ui_comprehensive.py --list

# Run ad-hoc Playwright scripts
docker exec puzzleboss-app python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('http://localhost/index.php?assumedid=testuser')
    print(page.title())
    browser.close()
"
```

**Load Testing**
```bash
# Configure test parameters
cp scripts/loadtest_config-EXAMPLE.yaml scripts/loadtest_config.yaml

# Run load tests (can run locally or in Docker)
python scripts/loadtest.py
```

## Common Operations

### Reset Hunt for New Event
```bash
# Preserves solver accounts, wipes puzzles/rounds/activity
python scripts/reset-hunt.py
```

### Database Schema Refresh
```bash
# WARNING: Destroys all data including solvers
mysql -u puzzleboss -p puzzleboss < scripts/puzzleboss.sql
```

### Email Inbox Monitoring
```bash
# Monitor IMAP inbox for hunt emails
python scripts/pbmail_inbox.py
```

### Wiki Indexing for RAG
```bash
# Index wiki content for LLM queries
python scripts/wiki_indexer.py
```

## Git Workflow

### Committing Changes
- Create commits with clear, descriptive messages
- Use co-authorship footer: `Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>`
- Commit frequently with logical groupings of changes
- Push to remote after each commit or set of related commits

### Critical Rules
**NEVER use `git reset` or `git rebase` unless absolutely necessary and with explicit user confirmation.**

These operations rewrite git history and can cause:
- Loss of work if not used carefully
- Confusion in collaboration with other developers
- Complications with remote branches that have already been pushed

**If you believe reset/rebase is necessary:**
1. Explain in detail WHY it's needed
2. Explain WHAT will happen
3. Provide alternative approaches if available
4. Wait for explicit user confirmation before proceeding

**Preferred alternatives:**
- New commits to fix mistakes (don't rewrite history)
- `git revert` to undo specific commits
- Create new branches instead of rebasing
- Use `git commit --amend` ONLY for the most recent unpushed commit

## Important Implementation Notes

### Authentication
- PHP frontend expects `REMOTE_USER` header from Apache (SSO/Kerberos/etc)
- For development/testing: Set `$noremoteusertestmode = "true"` in puzzlebosslib.php and use `?assumedid=username` URL param
- Ensure "testuser" exists in solvers table for dev mode

### API Design
- All endpoints return `{"status": "ok", ...}` on success
- Errors return `{"error": "message"}` with appropriate HTTP status codes
- Use `@swag_from` decorators in pbrest.py to reference API specs in `swag/` directory
- Swagger validation is automatic via Flasgger

### Integer ID Convention
All database IDs (puzzle.id, solver.id, round.id, activity.id) are `INT(11)` in MySQL and **must remain integers throughout the entire stack**: database → Python → JSON → API responses → frontend.

**Rules:**
- Every `pblib.py` function that accepts an ID parameter calls `int()` at the entry point, so callers can safely pass either `int` or `str` (e.g., Flask route params are always strings)
- JSON columns (`current_solvers`, `solver_history`) store `solver_id` as JSON number (`101`), never as JSON string (`"101"`). This matches how tags are stored in the `tags` column (`[42, 15, 8]`)
- SQL functions that extract IDs from JSON use `JSON_TABLE` with `INT PATH` (not `JSON_SEARCH` or `JSON_CONTAINS`, which are string-only)
- API response dicts must return `int(id)` for Flask route parameters (which arrive as strings), e.g., `{"id": int(id), ...}`
- MySQL's DictCursor returns native Python `int` for INT columns — do not convert with `str()`

**Why:** Python's `101 == "101"` is `False`, `json.dumps({"id": 101})` produces `101` (number) while `json.dumps({"id": "101"})` produces `"101"` (string), and JavaScript's `===` is type-strict. Mixing types causes silent comparison failures and inconsistent serialization.

**Tests:** `tests/test_pblib_id_types.py` guards all pblib functions against type regression. `tests/test_pblib_solver_assignment.py` guards JSON structure integrity.

**Migration:** Run `POST /migrate/normalize_solver_ids` to convert any legacy string solver_ids to integers in JSON columns.

### Database Access Patterns
- Use `mysql.connection` from Flask-MySQLdb (connection pooling built-in)
- Always commit after writes: `conn.commit()`
- Use parameterized queries: `cursor.execute("SELECT * FROM puzzle WHERE id=%s", (puzzle_id,))`
- UTF-8 support: `MYSQL_CHARSET = "utf8mb4"` is configured

### Google API Quota Management
- Hybrid metadata approach reduces quota usage significantly
- `pbgooglelib.py` tracks quota failures in `quota_failure_count` (thread-safe)
- bigjimmybot uses `BIGJIMMY_PUZZLEPAUSETIME` config to throttle requests
- Credentials auto-refresh via `creds.refresh(Request())`

### Logging
- Use `debug_log(severity, message)` from pblib.py
- Severity levels: 0=emergency, 1=error, 2=warning, 3=info, 4=debug, 5=trace
- Controlled via `LOGLEVEL` in config table
- Logs include timestamp, severity, function name, and message

### Memcache Integration
- Optional caching for `/allcached` endpoint (full puzzle/round data)
- Initialize via `init_memcache(configstruct)` after config is loaded
- Use `cache_get(key)` and `cache_set(key, value, ttl)` helpers (fail-safe)
- Default TTL: 60 seconds

### Multi-Process Considerations
- Gunicorn uses multiple workers (configured in gunicorn_config.py)
- Prometheus metrics use multiprocess mode via `prometheus_multiproc_dir`
- Wiki indexing uses file locking to prevent duplicate work across workers
- Config refresh is per-process but synchronized via database

### File Naming Conventions
- Python modules: lowercase with underscores (pb*.py for puzzleboss libraries)
- PHP files: lowercase (*.php)
- JavaScript: lowercase with hyphens (*.js)
- Swagger specs: lowercase action + noun (getpuzzles.yaml, postround.yaml)
- SQL schema: puzzleboss.sql

## Configuration Reference

### puzzleboss.yaml (Static)
- `MYSQL`: Database connection parameters
- `API.APIURI`: REST API endpoint (default: http://localhost:5000)

### config table (Dynamic)

**Current Hunt Adjustments** (change every year):
- `TEAMNAME`: Team display name
- `HUNT_FOLDER_NAME`: Google Drive folder name for current hunt

**Google API Settings**:
- `SKIP_GOOGLE_API`: Disable Google Sheets integration
- `GOOGLE_APPS_SCRIPT_CODE`: Apps Script code to deploy to puzzle sheets (defaults to simple onEdit tracker)
- `GOOGLE_APPS_SCRIPT_MANIFEST`: Apps Script manifest JSON (defaults to V8 runtime config)

**System Settings**:
- `LOGLEVEL`: Logging verbosity (0-5)
- `SKIP_PUZZCORD`: Disable Discord integration
- `MEMCACHE_ENABLED`, `MEMCACHE_HOST`, `MEMCACHE_PORT`: Memcache settings
- `PUZZCORD_HOST`, `PUZZCORD_PORT`: Discord bot connection
- `BIGJIMMY_PUZZLEPAUSETIME`: Delay between sheet polls (seconds)
- `WIKI_URL`, `WIKI_CHROMADB_PATH`: Wiki RAG configuration

## API Endpoint Patterns

- `/puzzles` - List all puzzles
- `/puzzles/<id>` - Get/update specific puzzle
- `/puzzles/<id>/<field>` - Update specific field (answer, status, etc)
- `/rounds` - List all rounds
- `/solvers` - List all solvers
- `/solvers/byname/<username>` - Lookup solver by username (efficient)
- `/activity` - Puzzle activity feed
- `/tags` - Tag management
- `/huntinfo` - Combined endpoint for config + statuses + tags (used by frontend)
- `/migrate` - List available data migrations (GET)
- `/migrate/<name>` - Run a named data migration (POST)
- `/v1/query` - LLM natural language queries (requires google-genai)
- `/metrics` - Prometheus metrics (requires prometheus_flask_exporter)

## Security Notes

- Never commit `puzzleboss.yaml`, `service-account.json`, `oidc-secrets.conf`
- Use environment variables or secrets management for production credentials
- Apache should restrict access to parent directory (only www/ should be web-accessible)
- Database user should only have access to puzzleboss database
- REMOTE_USER authentication is required for production (disable test mode)

## TODO / Future Work

### Promote `lastact` into `puzzle_view` and re-evaluate caching strategy
**Context:** The `/all` and `/allcached` endpoints return data from `puzzle_view`, which currently does NOT include `lastact` (last activity timestamp). The frontend fetches this separately. Promoting `lastact` into `puzzle_view` would let the cached response include it, reducing extra queries.

**Caching rule (current):** Cache is only invalidated for puzzle and round *structural* changes: status transitions, creation, deletion, round completion. Solver assignment/unassignment intentionally does NOT invalidate — the 15-second TTL (in `pbcachelib.py`) handles staleness for `cursolvers`. This keeps cache hit rates high during active solving (>90% observed during January 2026 hunt even with the old per-assignment invalidation).

**When `lastact` is added to `puzzle_view`:** The current simple single-key cache (`puzzleboss:all` in memcache) will need re-evaluation. Activity timestamps change constantly during a hunt. Options to consider:
- Per-puzzle cache keys (invalidate only the affected puzzle)
- Separate cache for static structure vs. volatile fields (lastact, cursolvers, sheetcount)
- Server-sent events or websocket push instead of polling + cache
- Hybrid: cache structural data with long TTL, overlay volatile fields from DB on each request

**Data point:** January 2026 hunt had >90% cache hit rate with 60s TTL and per-assignment invalidation. Current TTL is 15s with structural-only invalidation — monitor hit rate in next hunt to compare.
