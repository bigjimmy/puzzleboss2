# CLAUDE.md

Developer / agent guide for working on Puzzleboss 2000. Architecture, conventions, and workflows. Operator-facing docs live in [`docs/`](docs/):

- [docs/SETUP.md](docs/SETUP.md) — first-time install
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — running it day-to-day
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — when it breaks
- [docker/README.md](docker/README.md) — local Docker stack
- [docs/apps-script-deployment.md](docs/apps-script-deployment.md) — Apps Script add-on

Infrastructure (Terraform, ECS, Grafana dashboards, production runbook) is in a separate repo: [puzzleboss2-infra](https://github.com/bigjimmy/puzzleboss2-infra).

## Overview

Puzzleboss 2000 is a puzzle hunt management system: REST API backend (Python/Flask), web UI (PHP + Vue.js), Google Sheets integration, Discord bot integration, and an AI assistant bot (BigJimmy) for tracking solver activity.

## Architecture

### Backend (Python)

| File | Purpose |
|---|---|
| `pbrest.py` | Flask REST API. Main entry point for API operations. Uses Flasgger for Swagger/OpenAPI docs. |
| `pblib.py` | Core library: config management, solver assignment/unassignment, activity logging, email. Loads config from both `puzzleboss.yaml` (static) and database `config` table (dynamic). Config auto-refreshes every 30 seconds via `maybe_refresh_config()`. All functions that accept ID parameters normalize to `int()` at the boundary. |
| `pbgooglelib.py` | Google Drive/Sheets integration. Service account with Domain-Wide Delegation. Creates puzzle sheets, tracks sheet revisions. Hybrid metadata approach for activity tracking. |
| `pbdiscordlib.py` | Discord integration via socket connection to puzzcord daemon. |
| `pbllmlib.py` | LLM-powered natural-language queries via Google Gemini. Function calling + RAG via ChromaDB. |
| `pbcachelib.py` | Optional response cache (memcache today; [Redis migration planned](REDIS_MIGRATION.md)). Public API: `cache_get` / `cache_set` / `cache_delete` / `invalidate_all_cache`. |
| `bigjimmybot.py` | Long-running multi-threaded process. Polls Google Sheets for activity, updates puzzle metadata. Reads hidden `_pb_activity` sheet for sheets with add-on; falls back to Revisions API for legacy sheets. |
| `migrations/` | Data migration framework. See [scripts/migrations/README.md](scripts/migrations/README.md). |

### Frontend (PHP + JavaScript)

| File | Purpose |
|---|---|
| `www/puzzlebosslib.php` | Shared PHP library: API calls (`readapi`, `postapi`, `deleteapi`), `REMOTE_USER` auth, error handling. |
| `www/index.php` | Vue.js-based main UI: rounds, puzzles, real-time updates, filtering, tagging. |
| `www/*.php` | Pages for adding/editing puzzles, rounds, solvers, admin config. |
| `www/*.js` | Vue.js components: round display, tag selection, solve sounds. |
| `www/config.php` | **Authoritative reference** for all config-table keys and their descriptions. Don't duplicate this list elsewhere. |

### Database (MySQL)

Schema in [`scripts/puzzleboss.sql`](scripts/puzzleboss.sql). Key tables:

- `puzzle`, `round`, `solver`, `activity`, `tag`, `puzzle_tag`
- `config` — dynamic configuration (read every 30s)
- `botstats` — historical bot metrics
- `newuser` — pending signup records
- `privs` — admin role grants

### Integration points

- **Google Sheets activity (hybrid):** sheets with the Apps Script add-on write to a hidden `_pb_activity` sheet (quota-light); legacy sheets fall back to the Revisions API (quota-heavy). bigjimmybot checks `puzzle.sheetenabled` to decide. Full details in [docs/apps-script-deployment.md](docs/apps-script-deployment.md).
- **Configuration:** static bootstrap in `puzzleboss.yaml`, dynamic runtime in the `config` table. Both loaded in `pblib.refresh_config()`, stored in the global `configstruct` dict, refreshed periodically via `maybe_refresh_config()` on each API request.
- **Discord:** puzzcord daemon listens on a socket (host/port in config). Commands: `create_json`, `_round`, `_new`, `_solve`, `_attention`, `message`. Disable via `SKIP_PUZZCORD=true`.

### Optional features (toggled in `config` table)

- Google API (`SKIP_GOOGLE_API`)
- Memcache cache (`MEMCACHE_ENABLED`)
- Prometheus metrics (exposed at `/metrics` if `prometheus_flask_exporter` installed — it is in the dev/prod images)
- LLM queries (`/v1/query`, requires `google-genai`)
- Wiki RAG (`WIKI_URL`, `WIKI_CHROMADB_PATH`, requires `chromadb`)

## Development workflow

### Quickest path

```bash
docker-compose up --build
# Visit http://localhost?assumedid=testuser
```

See [docker/README.md](docker/README.md) for the full Docker reference. For native installs, [docs/SETUP.md#standalone-deployment](docs/SETUP.md#standalone-deployment).

### Running services manually

```bash
# API (dev)
python pbrest.py

# API (prod-style)
gunicorn -c gunicorn_config.py wsgi:app

# BigJimmy bot
python bigjimmybot.py

# PHP frontend (dev only)
cd www && php -S localhost:8080
```

Swagger UI is at <http://localhost:5000/apidocs> whenever the API is running.

## Testing

Run unit tests locally (no Docker needed — MySQL/Google APIs are mocked):

```bash
python3 -m pytest tests/ -v
python3 -m pytest tests/test_pblib_id_types.py -v   # specific file
```

API and UI integration tests require the Docker stack (PyYAML, Playwright, real DB):

```bash
# API tests
docker exec puzzleboss-app python /app/scripts/test_api_coverage.py --list
docker exec puzzleboss-app python /app/scripts/test_api_coverage.py --allow-destructive
docker exec puzzleboss-app python /app/scripts/test_api_coverage.py --allow-destructive --tests 1 5 10

# Solver assignment tests
docker exec puzzleboss-app python /app/scripts/test_solver_assignments.py

# UI tests (Playwright)
docker exec puzzleboss-app python /app/scripts/test_ui_comprehensive.py --list
docker exec puzzleboss-app python /app/scripts/test_ui_comprehensive.py --allow-destructive

# Ad-hoc Playwright
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

Test layout details in [`tests/README.md`](tests/README.md).

### Load testing

```bash
cp scripts/loadtest_config-EXAMPLE.yaml scripts/loadtest_config.yaml
python scripts/loadtest.py
```

## Conventions and rules

### Integer ID convention

All database IDs (`puzzle.id`, `solver.id`, `round.id`, `activity.id`) are `INT(11)` and **must remain integers throughout the entire stack**: database → Python → JSON → API responses → frontend.

Rules:

- Every `pblib.py` function that accepts an ID calls `int()` at the entry point — callers can pass either `int` or `str`.
- JSON columns (`current_solvers`, `solver_history`) store `solver_id` as JSON number (`101`), never as JSON string (`"101"`). Same as tag storage (`[42, 15, 8]`).
- SQL functions extracting IDs from JSON use `JSON_TABLE` with `INT PATH`, not `JSON_SEARCH` / `JSON_CONTAINS` (which are string-only).
- API response dicts return `int(id)` for Flask route parameters (which arrive as strings): `{"id": int(id), ...}`.
- MySQL's DictCursor returns native Python `int` for INT columns — don't `str()` them.

**Why:** Python's `101 == "101"` is `False`; `json.dumps({"id": 101})` produces `101` (number) but `{"id": "101"}` produces `"101"` (string); JavaScript's `===` is type-strict. Mixing types causes silent comparison failures and inconsistent serialization.

Guarded by `tests/test_pblib_id_types.py` and `tests/test_pblib_solver_assignment.py`. Legacy data can be normalized with `POST /migrate/normalize_solver_ids`.

### API design

- Success: `{"status": "ok", ...}`
- Failure: `{"error": "message"}` with appropriate HTTP status code
- Each endpoint references a `@swag_from('swag/<name>.yaml')` spec; Flasgger validates automatically.
- All endpoints require `REMOTE_USER` (or `?assumedid=` in dev mode with `ALLOW_USERNAME_OVERRIDE=true`).

### Database access

- Use `mysql.connection` from Flask-MySQLdb (connection pooling built-in)
- Always commit after writes: `conn.commit()`
- Use parameterized queries: `cursor.execute("SELECT * FROM puzzle WHERE id=%s", (puzzle_id,))`
- UTF-8: `MYSQL_CHARSET = "utf8mb4"`

### Logging

Use `debug_log(severity, message)` from `pblib.py`. Severity: 0=emergency, 1=error, 2=warning, 3=info, 4=debug, 5=trace. Controlled by `LOGLEVEL` in the config table. Logs include timestamp, severity, function name.

### Multi-process notes

- Gunicorn uses multiple workers (configured in `gunicorn_config.py`).
- Prometheus metrics use multiprocess mode via `prometheus_multiproc_dir`.
- Wiki indexing uses file locking to prevent duplicate work across workers.
- Config refresh is per-process but synchronized via the database.

### File naming

| Type | Convention |
|---|---|
| Python | lowercase_with_underscores (`pb*.py` for puzzleboss libraries) |
| PHP | lowercase (`*.php`) |
| JavaScript | lowercase-with-hyphens (`*.js`) |
| Swagger specs | `<verb><noun>.yaml` (`getpuzzles.yaml`) |
| SQL schema | `puzzleboss.sql` |

### Caching rules

Cache is invalidated **only** for puzzle and round *structural* changes: status transitions, creation, deletion, round completion. Solver assignment/unassignment intentionally does NOT invalidate — the 15-second TTL in `pbcachelib.py` handles staleness for `cursolvers` and `lastactcached`. This keeps hit rates high during active solving (>90% observed during January 2026 hunt with 60s TTL; current TTL is 15s).

## API endpoint patterns

| Endpoint | Purpose |
|---|---|
| `/puzzles` | List / create puzzles |
| `/puzzles/<id>` | Get / update a puzzle |
| `/puzzles/<id>/<field>` | Update one field |
| `/puzzles/stepwise` + `/createpuzzle/{code}?step=N` | Step-by-step creation (UI uses this) |
| `/puzzles/activate_all` | Re-deploy Apps Script add-on |
| `/rounds`, `/solvers`, `/activity`, `/tags` | Standard CRUD |
| `/solvers/byname/<username>` | Efficient lookup by name |
| `/huntinfo` | Combined config + statuses + tags (frontend bootstrap) |
| `/migrate` (GET) | List available migrations |
| `/migrate/<name>` (POST) | Run a migration |
| `/v1/query` | LLM natural-language query |
| `/metrics` | Prometheus metrics |
| `/all` | Full hunt state. Caches transparently — the hot path during a hunt. `/allcached` is a deprecated alias kept for backwards compatibility. |

## Git workflow

### Committing

- Clear, descriptive commit messages.
- Frequent commits with logical groupings.
- Push after each commit or related set of commits.

### Critical rules

**NEVER use `git reset` or `git rebase` unless absolutely necessary and with explicit user confirmation.** History rewrites lose work, confuse collaborators, and break already-pushed branches.

If you believe a rewrite is necessary:

1. Explain why.
2. Explain what will happen.
3. Offer alternatives.
4. Wait for explicit confirmation.

**Preferred alternatives:** new commits to fix mistakes; `git revert` to undo specific commits; new branches instead of rebasing; `git commit --amend` only for the most recent *unpushed* commit.

## Configuration reference

### `puzzleboss.yaml` (static, on disk)

- `MYSQL.*` — DB connection parameters
- `API.APIURI` — REST API endpoint

### `config` table (dynamic, refreshed every 30s)

The full reference lives in [`www/config.php`](www/config.php) (search for `$keyDescriptions`). Operator-facing summaries are in [docs/OPERATIONS.md](docs/OPERATIONS.md#the-config-table-tour). Don't duplicate the list here — it drifts.

## Security notes

- Never commit `puzzleboss.yaml`, `service-account.json`, `oidc-secrets.conf`. Service account credentials should live in the `SERVICE_ACCOUNT_JSON` config-table entry, not on disk.
- Use environment variables or secrets management for production credentials.
- Apache should restrict access to the parent directory (only `www/` should be web-accessible).
- The DB user should only have access to the `puzzleboss` database.
- `REMOTE_USER` authentication is required for production. Disable `ALLOW_USERNAME_OVERRIDE` in production.
