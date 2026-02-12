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

See `docker/README.md` for details, or continue reading for production setup.

## Production Setup

- git clone onto server
- Server-side prerequisites:
    - php
    - python >= 3.8
    - Apache (see below for config)
    - MySQL (see below for schema load and config instructions)

- Copy puzzleboss-SAMPLE.yaml to puzzleboss.yaml and edit for production:
    - Change MYSQL HOST from "mysql" to "127.0.0.1" (for native install)
    - Update MYSQL PASSWORD to a secure password
    - Update API endpoint if not using localhost:5000

- Apache config:
    - www subdir should be a web docroot or alias
    - www subdir should have PHP execution enabled
    - puzzleboss root dir should NOT be accessible via apache
    - User authentication should be configured in apache (we just need the REMOTE_USER header to be set)
    - Optionally proxy into swagger apidocs

- MySQL database:
    - Create database for puzzleboss to use (enter name in MYSQL.DATABASE in puzzleboss.yaml)
    - Create user with password for puzzleboss to use, and grant all permissions on above database
    - Import puzzleboss.sql (in scripts subdir) using mysql with the username and database created in above two steps (e.g. `mysql -u puzzleboss puzzleboss < puzzleboss.sql`)
    - IMPORTANT: above step will destroy previous database. If you'd like to preserve solvers table, use the reset-hunt script.

- Google Service Account Setup (optional):
    - Create a service account with Domain-Wide Delegation in Google Cloud Console
    - Download the JSON key file and place it in the app directory as `service-account.json`
    - Authorize the service account's client ID in Google Workspace Admin Console (Security → API controls → Domain-wide delegation) with Drive, Sheets, and Admin SDK scopes
    - Set `SERVICE_ACCOUNT_FILE` and `SERVICE_ACCOUNT_SUBJECT` in the config table
    - Set `HUNT_FOLDER_NAME` in the config table to the Google Drive folder name for puzzle sheets
    - Google integration can be disabled via `SKIP_GOOGLE_API` = `true` in the config table

- Running the REST API Service:
    - Start up pbrest.py: Will run on localhost:5000.
    - For actual multi-client use, install gunicorn and use the wsgi.py app object provided. Is safe to run on multiple servers at once for scale.

- Initial Configuration:
    - Make sure one solver is provisioned via normal account setup procedure and granted "puzztech" privileges via the admin UI or the privs table.
    - Use /pb/config.php to configure settings via the admin UI.
    - Alternatively use phpmyadmin or mysql access directly to update config values in the `config` table in the database.
    - Restart puzzleboss to make new config take effect.

- Swagger API Doc:
    - Is accessible at localhost:5000/apidocs (or appropriate proxied URL if behind a proxy) by running pbrest.py.
    - NOTE: if behind a proxy (e.g. in production), "try it out" functionality of swagger will not work

## Development/Testing Notes
- For testing as a different user, set `ALLOW_USERNAME_OVERRIDE` to `true` in the config table, then use `?assumedid=username` in the URL. The Docker setup enables this automatically.

- For running without a working puzzcord (discord bot) set `SKIP_PUZZCORD` to `true` in the config table.

- For running without Google Drive/Sheets, set `SKIP_GOOGLE_API` to `true` in the config table.

## Future TODOs

### Testing Infrastructure
- **Add pytest + mocking for unit tests**: Currently tests are integration tests requiring running API/DB. Future work should add pytest with mocking infrastructure to test business logic in isolation (mocking external dependencies like Google API, REST API calls, etc.). See `tests/test_bigjimmybot.py` for initial bigjimmybot unit tests as a template for expanding to pbrest.py, pbgooglelib.py, pbllmlib.py, etc.
