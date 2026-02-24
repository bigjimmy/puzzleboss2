#Puzzleboss 2000
---

**Description**: Puzzle solving team backend and interface developed by ATTORNEY for mystery hunts.

**Owner**: Benjamin O'Connor (benoc@alum.mit.edu)

## Quick Start (Docker)

For local development and testing, use Docker:

```bash
docker-compose up --build
```

Then visit http://localhost?assumedid=testuser

See `docker/README.md` for details.

## Production Deployment

This repo contains only application code. It is infrastructure-agnostic — you can deploy Puzzleboss to any environment that provides Apache+PHP, Python/Gunicorn, and a MySQL database.

### What you need

- **Apache** with PHP, `mod_auth_openidc` (or another auth mechanism that sets `REMOTE_USER`)
- **Python >= 3.8** with dependencies from `requirements.txt`
- **MySQL 8.x** with the schema from `scripts/puzzleboss.sql`
- **Configuration**: copy `puzzleboss-SAMPLE.yaml` → `puzzleboss.yaml` and edit for your environment

### Key files for production

| File | Purpose |
|------|---------|
| `Dockerfile.prod` | Multi-stage production image (Apache + Gunicorn in one container) |
| `wsgi.py` + `gunicorn_config.py` | Gunicorn entrypoint and config |
| `docker/prod/` | Production Apache config, supervisord config, entrypoint script |
| `deploy-ecs.sh` | Example deploy script for AWS ECS Fargate (builds, pushes to ECR, restarts services) |
| `deploy-legacy.sh` | Example deploy script for a single EC2/VM (git pull + systemd restart) |
| `scripts/puzzleboss.sql` | Database schema |
| `puzzleboss-SAMPLE.yaml` | Configuration template |

### Example: AWS ECS Fargate

The ATTORNEY team runs Puzzleboss on ECS Fargate. The infrastructure (Terraform, dashboards, operations runbook) is in a separate repo: [puzzleboss2-infra](https://github.com/bigjimmy/puzzleboss2-infra).

`deploy-ecs.sh` is the deploy script for that setup — it builds Docker images and pushes them to ECR. It auto-detects AWS account details and does not require Terraform to be co-located.

### Example: Standalone Server

For a simpler deployment on a single server (EC2, VM, bare metal):

1. Clone this repo onto the server
2. Install prerequisites: Apache (with PHP), Python >= 3.8, MySQL
3. `pip install -r requirements.txt`
4. `mysql -u puzzleboss puzzleboss < scripts/puzzleboss.sql`
5. Copy `puzzleboss-SAMPLE.yaml` → `puzzleboss.yaml`, configure MySQL connection
6. Run the API: `gunicorn -c gunicorn_config.py wsgi:app` (or `python pbrest.py` for dev)
7. Configure Apache: serve `www/` as docroot, set up user auth (`REMOTE_USER`), proxy `/api` to Gunicorn on port 5000

`deploy-legacy.sh` automates step 1 (pulls latest code from GitHub and restarts services via systemd).

### Optional integrations

- **Google Sheets**: set up a service account with Domain-Wide Delegation, place `service-account.json` in the app directory, configure via the `config` table. Disable with `SKIP_GOOGLE_API=true`.
- **Discord**: configure puzzcord connection in the `config` table. Disable with `SKIP_PUZZCORD=true`.
- **Swagger API docs**: accessible at `localhost:5000/apidocs` when the API is running.

## Development/Testing Notes
- For testing as a different user, set `ALLOW_USERNAME_OVERRIDE` to `true` in the config table, then use `?assumedid=username` in the URL. The Docker setup enables this automatically.

- For running without a working puzzcord (discord bot) set `SKIP_PUZZCORD` to `true` in the config table.

- For running without Google Drive/Sheets, set `SKIP_GOOGLE_API` to `true` in the config table.

## Future TODOs

### Testing Infrastructure - Unit Tests for Core Libraries

**Current Test Coverage:**
- ✅ pbrest.py: 28/28 API integration tests (100% coverage via end-to-end tests)
- ✅ bigjimmybot.py: 26/26 unit tests with mocking (100% coverage)
- ✅ pblib.py: 27/27 unit tests — solver assignment behavior + ID type normalization
- ✅ rate_limiter.py: 10/10 unit tests — timing, config, thread safety
- ✅ UI workflows: 27/27 Playwright tests (100% coverage)
- ⚠️ pbgooglelib.py: No unit tests (integration tested via bigjimmybot/pbrest)
- ⚠️ pbllmlib.py: No unit tests (integration tested via API endpoints)

**Recommended: Add unit tests for remaining targets**
1. **pbgooglelib.py** (High Priority): Complex Google API logic (Drive/Sheets/Revisions), quota management, error handling. Unit tests would enable testing without actual Google API access and cover edge cases.
2. **pbllmlib.py** (High Priority): LLM query logic, function calling, RAG integration. Unit tests can mock AI responses to test parsing and error handling.

**Note:** pbrest.py unit tests are LOW priority - already has comprehensive end-to-end API test coverage (28 tests). Adding unit tests would duplicate coverage without significant benefit since pbrest is now thin wrappers around pblib functions.

**Template:** See `tests/test_bigjimmybot.py` for pytest + mocking patterns (mocks MySQLdb, HTTP calls, external dependencies).
