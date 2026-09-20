# CLAUDE.md

Developer / agent guide for working on Puzzleboss 2000. Architecture, conventions, and workflows. Operator-facing docs live in [`docs/`](docs/):

- [docs/SETUP.md](docs/SETUP.md) — first-time install
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — running it day-to-day
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — when it breaks
- [docker/README.md](docker/README.md) — local Docker stack
- [docs/apps-script-deployment.md](docs/apps-script-deployment.md) — Apps Script add-on

Infrastructure (Terraform, ECS, Grafana dashboards, production runbook) is in a separate repo: [puzzleboss2-infra](https://github.com/benoc617/puzzleboss2-infra).

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
| `pbcachelib.py` | Optional Redis cache: the `/all` blob (15s TTL) plus the write-through `lastact` hash and the rebuild lock. Public API: `cache_get` / `cache_set` / `cache_delete` / `invalidate_all_cache` / `lastact_*` / rebuild-lock helpers. See [REDIS_MIGRATION.md](REDIS_MIGRATION.md). |
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

**Key indexes:** `activity` has two composite indexes. `idx_puzzle_time (puzzle_id, time)` turns the per-puzzle "latest activity" query (and the `/all` cold-start `GROUP BY puzzle_id` that rebuilds the lastact hash) into a loose index scan — cost scales with puzzle count, not total activity rows. `idx_solver_time (solver_id, time)` does the same for `get_last_activity_for_solver`, which bigjimmybot calls per new activity record. Added by the corresponding `migrations/add_activity_*_index.py` migrations and present in the schema. Critical for performance as activity grows during a hunt.

### Integration points

- **Google Sheets activity (hybrid):** sheets with the Apps Script add-on write to a hidden `_pb_activity` sheet (quota-light); legacy sheets fall back to the Revisions API (quota-heavy). bigjimmybot checks `puzzle.sheetenabled` to decide. Full details in [docs/apps-script-deployment.md](docs/apps-script-deployment.md).
- **Configuration:** static bootstrap in `puzzleboss.yaml`, dynamic runtime in the `config` table. Both loaded in `pblib.refresh_config()`, stored in the global `configstruct` dict, refreshed periodically via `maybe_refresh_config()` on each API request.
- **Discord:** puzzcord daemon listens on a socket (host/port in config). Commands: `create_json`, `_round`, `_new`, `_solve`, `_attention`, `message`. Disable via `SKIP_PUZZCORD=true`.

### Optional features (toggled in `config` table)

- Google API (`SKIP_GOOGLE_API`)
- Redis cache (`REDIS_ENABLED`, `REDIS_HOST`, `REDIS_PORT`)
- Prometheus metrics (exposed at `/metrics` if `prometheus_flask_exporter` installed — it is in the dev/prod images)
- LLM queries (`/v1/query`, requires `google-genai`)
- Wiki RAG (`WIKI_URL`, `WIKI_CHROMADB_PATH`, `GEMINI_EMBEDDING_MODEL`, requires `chromadb`). The embedding model is stamped into the ChromaDB collection metadata; changing it requires `scripts/wiki_indexer.py --full`, and `search_wiki` refuses a mismatched index.

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
- All endpoints require `REMOTE_USER` (or `?assumedid=` in dev mode with `ALLOW_USERNAME_OVERRIDE=true` — honored **only from puzzleboss.yaml**, never from the config table, so a runtime config write can't enable impersonation).
- **Admin endpoints are token-gated** via the `admin_token_gated` decorator: `POST /config`, `POST /rbac/*`, `GET /deleteuser`, `DELETE /deletepuzzle`, `POST /migrate/*`, `GET /newusers`, `GET /google/users` require `X-PB-Internal-Token`. Enforcement is controlled by the `ADMIN_TOKEN_ENFORCE` config key (false = warn-only rollout mode: log and allow; true = 403). The PHP tier attaches the token via `postapi_internal`/`deleteapi_internal`/`readapi_internal` — always AFTER a puzztech check (the token authenticates the server tier, not the user).
- `puzzle_uri` must start with `http://` or `https://` at write time (creation and part-update paths).

### Database access

- Use `mysql.connection` from Flask-MySQLdb (one connection per request — there is NO pooling; expect ~40ms connection setup with SSL)
- Always commit after writes: `conn.commit()`
- Use parameterized queries: `cursor.execute("SELECT * FROM puzzle WHERE id=%s", (puzzle_id,))`
- **SQL identifiers are never interpolated from request data.** Endpoints that take a column/field name from the URL or JSON (`/puzzles/<id>/<part>`, solver/round part updates, `/rbac/<priv>`, `pblib.update_puzzle_field`) validate it against a schema-tracking frozenset allowlist (`PUZZLE_VIEW_COLUMNS`, `ROUND_UPDATABLE_COLUMNS`, `SOLVER_UPDATABLE_COLUMNS`, `PRIV_COLUMNS` in pbrest.py; `PUZZLE_UPDATABLE_COLUMNS` in pblib.py) and 400 on miss. When the schema changes, update the allowlists.
- UTF-8: `MYSQL_CHARSET = "utf8mb4"`

### Logging

Use `debug_log(severity, message)` from `pblib.py`. Severity: 0=emergency, 1=error, 2=warning, 3=info, 4=debug, 5=trace. Controlled by `LOGLEVEL` in the config table. Logs include timestamp, severity, function name.

### Multi-process notes

- Gunicorn uses multiple workers (configured in `gunicorn_config.py`).
- Prometheus metrics use multiprocess mode via `prometheus_multiproc_dir`.
- Wiki indexing uses file locking to prevent duplicate work across workers.
- Config refresh is per-process but synchronized via the database. Refresh failures raise and are swallowed by `maybe_refresh_config()` — the worker keeps serving with stale config; only the initial startup load is fatal (`sys.exit(255)`). A transient DB blip must never kill workers.
- Discord announces (`chat_announce_*`) are best-effort: wrapped in try/except at call sites, and DB mutations (answer, activity, round completion) always happen BEFORE Discord I/O in the solve paths.

### File naming

| Type | Convention |
|---|---|
| Python | lowercase_with_underscores (`pb*.py` for puzzleboss libraries) |
| PHP | lowercase (`*.php`) |
| JavaScript | lowercase-with-hyphens (`*.js`) |
| Swagger specs | `<verb><noun>.yaml` (`getpuzzles.yaml`) |
| SQL schema | `puzzleboss.sql` |

### Caching rules

The `/all` blob is invalidated **only** for *structural* changes — enforced by the `STRUCTURAL_PUZZLE_FIELDS` allowlist in `pblib.update_puzzle_field` (status, name, round_id, answer, ismeta) plus create/delete, round operations, and puzzle tag add/remove/delete (which write `puzzle.tags` directly and invalidate explicitly, since the UI filters on tags immediately). Everything else (xyzloc, comments, sheetcount, solver assignment) rides the 15-second TTL. This keeps hit rates high during active solving (>90% observed during January 2026 hunt).

Per-puzzle `lastact` is NOT cached in the blob: it lives in a write-through Redis hash (`puzzleboss:lastact`), updated by `pblib.log_activity()` on every activity insert and attached fresh to every `/all` response — always current, never invalidated. Cold-start fallback is the indexed GROUP BY over `activity(puzzle_id, time)`. A `SET NX` rebuild lock prevents miss stampedes.

Cache behavior is observable via botstats counters (in `METRICS_METADATA`, exposed through `metrics.php` → Prometheus → the `redis-cache` Grafana dashboard): `cache_hits_total`, `cache_misses_total`, `cache_invalidations_total`, `cache_rebuild_lock_contentions_total`, `cache_write_through_failures_total`, `cache_cold_start_backfills_total`.

## API endpoint patterns

| Endpoint | Purpose |
|---|---|
| `/puzzles` | List / create puzzles |
| `/puzzles/<id>` | Get / update a puzzle |
| `/puzzles/<id>/<field>` | Update one field |
| `/puzzles/stepwise` + `/createpuzzle/{code}?step=N` | Step-by-step creation (UI uses this) |
| `/puzzles/activate_all` | Re-deploy Apps Script add-on |
| `/rounds`, `/solvers`, `/tags` | Standard CRUD |
| `/activity`, `/activitysearch` | Activity log (read-only; activitysearch takes filters + LIMIT) |
| `/search` | Puzzle search by tag / tag_id |
| `/hints`, `/hints/<id>/*` | Hint queue: solver submission, answer/demote/delete (admin ops puzztech-gated in the PHP proxy) |
| `/rbac/<priv>/<uid>` | Privilege check (GET) / grant-revoke (POST, token-gated) |
| `/config` | Config table read (secrets redacted) / write (token-gated) |
| `/account`, `/finishaccount/<code>`, `/newusers` | Signup lifecycle (newusers is token-gated) |
| `/cache/invalidate` | Force /all cache invalidation |
| `/solvers/byname/<username>` | Efficient lookup by name |
| `/huntinfo` | Combined config + statuses + tags (frontend bootstrap; config secrets always redacted) |
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
- `API.INTERNAL_TOKEN` — shared token for unredacted `/config` reads and the token-gated admin endpoints (see Security notes). Env var `INTERNAL_TOKEN` overrides it.
- `ALLOW_USERNAME_OVERRIDE` — deploy-time only; enables `?assumedid=` impersonation for dev. Honored ONLY from this file — the config-table row is ignored.

### `config` table (dynamic, refreshed every 30s)

The full reference lives in [`www/config.php`](www/config.php) (search for `$keyDescriptions`). Operator-facing summaries are in [docs/OPERATIONS.md](docs/OPERATIONS.md#the-config-table-tour). Don't duplicate the list here — it drifts.

## Security notes

- Never commit `puzzleboss.yaml`, `service-account.json`, `oidc-secrets.conf`. Service account credentials should live in the `SERVICE_ACCOUNT_JSON` config-table entry, not on disk.
- Use environment variables or secrets management for production credentials.
- **Config secret redaction:** `GET /config` and `GET /huntinfo` redact secret values to `"********"` — see `pblib.redact_config`. Secrecy classification is **flag as authority, heuristic as fallback**: the `config.secret` column (operator-editable via the 🔒 toggle in `config.php`, or `POST /config` with a boolean `secret` field) is the authoritative signal, OR'd with the name-pattern heuristic (`pblib.is_secret_config_key`: `API_KEY`/`SECRET`/`PASSWORD`/`TOKEN`/`WEBHOOK` substrings + `SERVICE_ACCOUNT_JSON`) so a forgotten flag on a conventionally-named key still fails closed. The `/config` response's `secret_keys` field exposes the combined classification so client display logic never drifts from the server. Value-only `POST /config` writes preserve the existing flag. Backfilled by [`migrations/add_config_secret_flag.py`](migrations/add_config_secret_flag.py); pre-migration databases get heuristic-only redaction (the API logs a warning rather than failing). Trusted server-side consumers (`config.php` admin page, `account/index.php` signup, `pbmail_inbox.py`) get unredacted `/config` by sending `X-PB-Internal-Token` matching `API.INTERNAL_TOKEN` (fail-closed if unconfigured; `hmac.compare_digest`; unredacted reads are logged with `X-Remote-User`). The token authenticates the server-side *tier* — user-level authz (puzztech) stays in the PHP layer, which checks privs before attaching it. Secrets Manager / SSM provisions the token at deploy time only; nothing fetches from AWS at runtime.
- **Admin endpoint gating:** the same internal token gates the destructive/admin API endpoints (`POST /config`, `POST /rbac/*`, `/deleteuser`, `/deletepuzzle`, `POST /migrate/*`, `/newusers`, `/google/users`) via the `admin_token_gated` decorator. `ADMIN_TOKEN_ENFORCE=true` in the config table enforces 403; false/absent logs a SEV2 warning and allows (rollout mode). Production runs enforced. PHP attaches the token only from puzztech-gated code paths (`*api_internal` helpers in `puzzlebosslib.php`).
- **CSRF:** double-submit cookie (`pb_csrf`, set by `puzzlebosslib.php`). JS fetch wrappers send `X-PB-CSRF`; form-POST pages embed `pb_csrf_field()` and verify with `pb_verify_csrf()`. Every mutating `apicall.php` call requires the header. New mutating pages/fetches must participate.
- **XSS:** escape all request/API data echoed into HTML with `htmlspecialchars()` (see `search.php` for the pattern); solver names into inline JS via `json_encode()`; Vue `:href` bindings of user-supplied URIs must be scheme-checked (`^https?://`) — the API also rejects non-http(s) `puzzle_uri` at write time.
- Apache should restrict access to the parent directory (only `www/` should be web-accessible).
- The DB user should only have access to the `puzzleboss` database.
- `REMOTE_USER` authentication is required for production. `ALLOW_USERNAME_OVERRIDE` is read from `puzzleboss.yaml` only (a DB config row is ignored with a warning) — omit it or set `"false"` in production; docker dev sets `"true"` for `?assumedid=`.
