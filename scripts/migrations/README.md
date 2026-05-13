# Database migrations

Puzzleboss has **two** complementary places for migrations. Use the right one for the job.

## `migrations/` (Python, API-driven) — preferred

Idiomatic location for schema and data changes that ship with application code.

- Each migration is a Python module in [`/migrations/`](../../migrations/) exporting `name`, `description`, and `run(conn)`.
- Discoverable via `GET /migrate`.
- Executable via `POST /migrate/<name>`.
- Must be **idempotent** — safe to re-run.
- Intended to be **pruned** once they have been run everywhere they need to be run.

Example:

```bash
curl http://localhost:5000/migrate
curl -X POST http://localhost:5000/migrate/normalize_solver_ids
```

To add one, drop a new module in [`/migrations/`](../../migrations/) following the pattern of existing files — see [`migrations/add_recaptcha_config.py`](../../migrations/add_recaptcha_config.py) as a small template.

## `scripts/migrations/` (raw SQL) — for things that don't fit the framework

This directory holds raw `.sql` files. Use it when:

- The change is too low-level for a Python module (e.g. function/procedure rewrites, complex DDL).
- The change has to run before the application can start (so an API-driven migration can't reach it).
- You need to apply it manually during an upgrade with `mysql -u puzzleboss -p puzzleboss < file.sql`.

Files here aren't auto-discovered — they're documentation for a one-time manual step. They should also be **idempotent** (use `IF NOT EXISTS`, `DROP ... IF EXISTS`, etc.).

## Migration discipline

Whichever directory you put it in:

1. Always back up the database first:

   ```bash
   mysqldump -u puzzleboss -p puzzleboss > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. Test the migration in Docker / a staging environment before running it in production.

3. Run during low-traffic periods when possible.

4. After it's been applied everywhere, **prune the file** in a follow-up commit. Migrations are not history — they accumulate noise and confuse future readers. The change is already permanently captured in the schema and the git log.

5. Watch logs and metrics for at least a few minutes after running anything destructive.
