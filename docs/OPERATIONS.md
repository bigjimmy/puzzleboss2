# Operations guide

For the person operating an already-running Puzzleboss instance — typically a new admin inheriting it from a previous one, or someone preparing for the upcoming hunt.

If you're standing it up for the first time, see [SETUP.md](SETUP.md) first. If it's broken right now, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## What you need to know first

- **Configuration lives in two places.** `puzzleboss.yaml` on disk holds bootstrap info (MySQL connection, API URL). The `config` table in MySQL holds everything else — team name, integration toggles, credentials, feature settings. The dynamic config refreshes every 30 seconds, so changes via the admin UI take effect within a minute without a restart.
- **The infra is in a separate repo.** Terraform, Grafana dashboards, ECS task definitions, deploy scripts, and the production-operations runbook live in [puzzleboss2-infra](https://github.com/bigjimmy/puzzleboss2-infra). This repo only contains application code.
- **Most issues during a hunt are integration issues, not application bugs.** Google quota, Discord rate limits, sheets-add-on failures. Watch [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Request flow

```mermaid
sequenceDiagram
    participant Browser
    participant Apache
    participant PHP as PHP frontend
    participant Gunicorn
    participant MySQL
    participant Google
    Browser->>Apache: GET /index.php
    Apache->>PHP: REMOTE_USER header set by OIDC
    PHP->>Gunicorn: curl APIURI (server-side, localhost)
    Gunicorn->>MySQL: SELECT ...
    MySQL-->>Gunicorn: rows
    Gunicorn-->>PHP: JSON
    PHP-->>Apache: rendered HTML
    Apache-->>Browser: rendered page
    Browser->>Apache: fetch apicall.php?apicall=...
    Apache->>PHP: same flow, PHP curls API
    Note over Browser,Google: The Flask API is never reached directly<br/>from the browser in production — PHP<br/>(apicall.php) mediates every call.<br/>BigJimmy bot runs separately, polls<br/>Google Sheets and writes activity via the API.
```

## The components you operate

| Component | What it is | Where it lives | Notes |
|---|---|---|---|
| Web UI | Apache + PHP | inside the app container/server | What users see |
| API | Gunicorn + Flask | same container as Apache, bound to localhost:5000 | Not exposed externally in prod — PHP mediates browser → API via `apicall.php` |
| BigJimmy bot | Watches every active puzzle's Google Sheet for edits, auto-assigns solvers to whichever puzzle they're working on, marks idle puzzles abandoned, and updates `sheetcount` / `lastsheetact` metadata used by the UI | `[program:bigjimmybot]` in supervisord | Enabled in production; disabled in the local dev stack (flip `autostart=true` in `docker/supervisord.conf`) |
| MySQL | The database | RDS in prod, container locally | Schema in [`scripts/puzzleboss.sql`](../scripts/puzzleboss.sql) |
| OIDC cache | Session storage for mod_auth_openidc | currently memcache, [Redis migration planned](../REDIS_MIGRATION.md) | Hard failure = login broken |
| Response cache | `/all` endpoint cache (the hot path) | same cache backend | Soft failure = falls through to DB. `/allcached` is a deprecated alias. |
| MediaWiki | Team wiki | separate container, shares auth | Optional |
| Observability stack | Loki + Grafana + Prometheus | separate EC2 in infra repo | See [observability](#observability) |

## The config table tour

Edit configuration through the **Configuration Management** page (`/config.php`, gated by the `puzztech` priv) — long values like `bookmarklet_js` and `GEMINI_SYSTEM_INSTRUCTION` are textareas there. There's no need to touch MySQL directly; the UI is the supported path. The full key list and descriptions are loaded from [`www/config.php`](../www/config.php) (the `$keyDescriptions` array) — that's the canonical reference.

Below are the keys you'll actually touch, grouped:

### Annual / per-hunt

| Key | Action |
|---|---|
| `TEAMNAME` | Display name |
| `HUNT_FOLDER_NAME` | Drive folder for this year's puzzle sheets |
| `BIGJIMMY_AUTOASSIGN` | Set `true` for hunts where you want auto-assignment |
| `hunt_domain` | Domain of the hunt website (for the bookmarklet) |
| `bookmarklet_js` | The bookmarklet itself. **Expect to rewrite this every hunt** — it scrapes puzzle title, slug, and round name out of the hunt site's DOM, and every hunt's site is different (different selectors, different window globals like `window.initialTeamState`, sometimes a totally different framework). Test as soon as the hunt site is up. Edit via the **Configuration Management** page (the `bookmarklet_js` field is a textarea). |

### Integration toggles

| Key | Effect when `true` |
|---|---|
| `SKIP_GOOGLE_API` | Disables all Google Drive/Sheets — puzzles get no sheets |
| `SKIP_PUZZCORD` | Disables Discord |
| `ALLOW_USERNAME_OVERRIDE` | **Test mode** — `?assumedid=` works. Keep `false` in production. |
| `MEMCACHE_ENABLED` | Enables the `/all` response cache |

### Bot tuning

| Key | What |
|---|---|
| `BIGJIMMY_PUZZLEPAUSETIME` | Seconds between sheet polls per puzzle (default 1) |
| `BIGJIMMY_THREADCOUNT` | Parallel sheet-polling threads (default 2) |
| `BIGJIMMY_GOOGLE_API_QPM` | Soft rate limit for Google API calls (default 55) |
| `BIGJIMMY_QUOTAFAIL_DELAY` / `BIGJIMMY_QUOTAFAIL_MAX_RETRIES` | Backoff on 429s |
| `BIGJIMMY_ABANDONED_TIMEOUT_MINUTES` | When to mark idle puzzles abandoned |

## Common admin tasks

### Reset for a new hunt

```bash
python scripts/reset-hunt.py
```

Backs up the database to `scripts/backups/`, then wipes puzzles, rounds, and activity. **Solvers, privileges, and config are preserved**, so you don't need to re-onboard people.

Then in the **Configuration Management** UI (`/config.php`):

- Update `HUNT_FOLDER_NAME` to the new Drive folder (e.g. `Hunt 2027`).
- Update `hunt_domain` to the new hunt site domain.
- Rewrite `bookmarklet_js` to match the new hunt site's DOM — see the per-hunt config table above. This almost always needs to change. Test it against the new hunt site as soon as the site is up.

### Add an admin

Open the **Accounts Management** page (`/accounts.php`, requires `puzztech` priv). Each solver has clickable **PT** (puzztech) and **PB** (puzzleboss) priv columns — click to toggle. `puzzleboss` is the admin role for puzzle/round operations; `puzztech` is the technical-admin role for editing config, managing users, and granting privs.

### Recover from a lost / departed admin account

If every `puzztech` admin has left the team (or was deactivated upstream in OIDC), nobody can use the Accounts Management UI to grant a new one. You need direct MySQL access:

```sql
-- Find the solver who should become the new admin
SELECT id, name, fullname FROM solver WHERE name='new-admin-username';

-- Promote them (upsert: works whether they already had a privs row or not)
INSERT INTO privs (uid, puzztech, puzzleboss) VALUES (<id>, 'YES', 'YES')
  ON DUPLICATE KEY UPDATE puzztech='YES', puzzleboss='YES';
```

The same approach works if a former admin's account needs to be **demoted** for hygiene (set both columns to `'NO'`) — though that can also be done from the UI by any remaining `puzztech` admin.

### Bulk-import solvers

`POST /solvers` with a JSON body — see Swagger at `/apidocs` for the schema. For bigger imports, write a one-off script that hits the API.

### Run a data migration

When the application code introduces a schema or data change, it ships with a migration module under [`migrations/`](../migrations/) (see [`scripts/migrations/README.md`](../scripts/migrations/README.md) for the migration system).

```bash
# List available migrations
curl http://localhost:5000/migrate

# Run one
curl -X POST http://localhost:5000/migrate/<name>
```

Migrations are idempotent. Production-style: backup first (`mysqldump`), then run.

### Edit the Apps Script add-on

The add-on code lives in the `GOOGLE_APPS_SCRIPT_CODE` config value. Updating it only affects **new** puzzle sheets — to update existing ones, re-deploy via `POST /puzzles/activate_all`. Full details in [apps-script-deployment.md](apps-script-deployment.md).

## Observability

The production observability stack runs on a dedicated EC2 instance, configured via Terraform in the infra repo. The current host details (IP, SSH port, instance ID) live there — don't hardcode them here.

### What it gives you

| Tool | Purpose | Where |
|---|---|---|
| **Grafana** | Dashboards, alerting | served from the obs host |
| **Loki** | Centralized logs, queried via LogQL | ECS containers ship via FireLens + Fluent Bit |
| **Prometheus** | Metrics, scraped from `/metrics` | scrapes the app container |

### Log labels to know

- `service=bigjimmy` — bot logs
- `service=puzzleboss` — Apache + Gunicorn logs (web + API)
- `service=mediawiki` — wiki container
- `service=puzzcord` — Discord daemon (if shipping there)

A typical query:

```logql
{service="puzzleboss"} |= "ERROR" | json
```

### Useful metrics

`/metrics` on the app container exposes:

- `bigjimmy_loop_time_seconds` — total time for last bot iteration
- `bigjimmy_quota_failures` — counter for Google 429s
- `bigjimmy_loop_puzzle_count` — puzzles processed last loop
- `cache_invalidations_total` — counter
- `puzzcord_members_active_anywhere` — gauge of currently-active solvers

The `botstats` table also holds historical metric data — `METRICS_METADATA` in the config table defines what's exposed.

## Deployment

Deployment is automated via GitHub Actions in this repo. Pushing to `master` builds new container images. The actual ECS rollout is triggered manually from the **Deploy** workflow (or via the deploy script in the infra repo). See [`.github/workflows/`](../.github/workflows/) for the workflow definitions.

For local/Docker development, no deployment — just `docker-compose up`.

## Backups

`scripts/reset-hunt.py` makes a timestamped backup before wiping. For ad-hoc backups:

```bash
mysqldump -u puzzleboss -p puzzleboss > backup_$(date +%Y%m%d_%H%M%S).sql
```

In production, RDS automated backups handle PITR. Snapshot before any large migration.

## Off-season

Between hunts:

- Keep the app + DB running (cheap) so signups still work and solvers can find old data.
- Or scale ECS service `desiredCount` to 0 (see infra repo) and bring back up a few weeks before the next hunt.
- Keep an eye on Google quota — DWD service-account keys don't expire but the JSON can be rotated. The `SERVICE_ACCOUNT_JSON` config value is what to update.

## What's normal during a hunt

- BigJimmy will occasionally hit 429s. As long as `bigjimmy_quota_failures` isn't climbing fast, it's fine — backoff handles it.
- Sheet add-on deploys can rate-limit when many puzzles are created at once. Retries happen automatically; failed sheets can be retried with `POST /puzzles/activate_all`.
- Some puzzles end up "Abandoned" when solvers idle on them. That's the `BIGJIMMY_ABANDONED_TIMEOUT_MINUTES` setting doing its job.
- The `/all` endpoint is the hot path during heavy traffic; it caches transparently and a hit rate over 90% with the default 15s TTL is normal.

## What's not normal

Anything in [TROUBLESHOOTING.md](TROUBLESHOOTING.md). Read it before the hunt starts.
