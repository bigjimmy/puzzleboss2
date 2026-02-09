# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Puzzleboss 2000 is a puzzle hunt management system developed by ATTORNEY for mystery hunt teams. It provides a REST API backend (Python/Flask), web UI (PHP/JavaScript/Vue.js), Google Sheets integration, Discord bot integration, and an AI assistant bot (BigJimmy) for tracking solver activity.

## Architecture

### Core Components

**Backend (Python)**
- `pbrest.py` - Flask REST API server with MySQL database. Main entry point for API operations. Uses Flasgger for Swagger/OpenAPI documentation.
- `pblib.py` - Core library with configuration management, logging utilities, and email functions. Loads config from both `puzzleboss.yaml` (static) and database `config` table (dynamic). Config auto-refreshes every 30 seconds via `maybe_refresh_config()`.
- `pbgooglelib.py` - Google Drive/Sheets integration. Manages OAuth credentials (`token.json`), creates puzzle sheets, tracks sheet revisions. Supports hybrid metadata approach for sheet activity tracking.
- `pbdiscordlib.py` - Discord integration via socket connection to puzzcord daemon. Creates channels, announces solves/rounds.
- `pbllmlib.py` - LLM-powered natural language queries via Google Gemini. Includes function calling for hunt data and RAG support for wiki content via ChromaDB.
- `bigjimmybot.py` - Multi-threaded bot that polls Google Sheets for activity and updates puzzle metadata (sheetcount, lastsheetact). Uses hybrid approach: legacy Revisions API for old sheets, DeveloperMetadata API for sheets with `sheetenabled=1`.

**Frontend (PHP + JavaScript)**
- `www/puzzlebosslib.php` - Shared PHP library for API calls (`readapi`, `postapi`, `deleteapi`), authentication via `REMOTE_USER` header, and error handling.
- `www/index.php` - Main Vue.js-based UI showing rounds and puzzles with real-time updates, filtering, and tagging.
- `www/*.php` - Various UI pages for adding/editing puzzles, rounds, solvers, admin config, etc.
- `www/*.js` - Vue.js components for round display, tag selection, solve sounds.

**Database (MySQL)**
- Schema defined in `scripts/puzzleboss.sql`
- Key tables: `puzzle`, `round`, `solver`, `activity`, `tag`, `puzzle_tag`, `config`, `botstats`, `newuser`, `privs`
- `config` table stores runtime configuration that can be modified via admin UI
- `puzzle.sheetenabled` column indicates if sheet has DeveloperMetadata enabled (hybrid approach)

### Key Integration Points

**Google Sheets Activity Tracking (Hybrid Approach)**
- Old approach: `get_puzzle_sheet_info_legacy()` in pbgooglelib.py uses Revisions API (quota-heavy)
- New approach: `get_puzzle_sheet_info()` uses DeveloperMetadata API (quota-light)
- bigjimmybot.py checks `puzzle.sheetenabled` column to decide which method to use
- When DeveloperMetadata is detected on a sheet with `sheetenabled=0`, bigjimmybot automatically enables it via POST to `/puzzles/{id}/sheetenabled`

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

### Google Sheets Setup (Optional)
```bash
# 1. Get credentials.json from Google Cloud Console
# 2. Generate token.json
python gdriveinit.py

# 3. For admin features (user provisioning)
python googleadmininit.py
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

**API Integration Tests**
```bash
# Comprehensive test suite covering all endpoints
python scripts/test_api_coverage.py

# Test solver assignment logic
python scripts/test_solver_assignments.py
```

**Load Testing**
```bash
# Configure test parameters
cp scripts/loadtest_config-EXAMPLE.yaml scripts/loadtest_config.yaml

# Run load tests
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
Key config variables:
- `LOGLEVEL`: Logging verbosity (0-5)
- `TEAMNAME`: Team display name
- `HUNT_FOLDER_NAME`: Google Drive folder name
- `SKIP_GOOGLE_API`: Disable Google Sheets integration
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
- `/v1/query` - LLM natural language queries (requires google-genai)
- `/metrics` - Prometheus metrics (requires prometheus_flask_exporter)

## Security Notes

- Never commit `puzzleboss.yaml`, `credentials.json`, `token.json`, `admintoken.json`
- Use environment variables or secrets management for production credentials
- Apache should restrict access to parent directory (only www/ should be web-accessible)
- Database user should only have access to puzzleboss database
- REMOTE_USER authentication is required for production (disable test mode)
