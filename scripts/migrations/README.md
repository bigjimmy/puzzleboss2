# Production Database Migrations

This directory contains SQL migration scripts for applying database schema changes to production without performing a full reset.

## Running Migrations

### For PR #102 (Stepwise Puzzle Creation)

**Command:**
```bash
mysql -u puzzleboss -p puzzleboss < scripts/migrations/add_temp_puzzle_creation.sql
```

**What it does:**
- Creates the `temp_puzzle_creation` table
- This table stores puzzle data during step-by-step creation process
- Safe to run multiple times (uses `CREATE TABLE IF NOT EXISTS`)

**Verification:**
```sql
USE puzzleboss;
SHOW TABLES LIKE 'temp_puzzle_creation';
DESCRIBE temp_puzzle_creation;
```

Expected output:
```
+-------------------+
| Tables_in_puzzleboss (temp_puzzle_creation) |
+-------------------+
| temp_puzzle_creation |
+-------------------+

+-------------------+--------------+------+-----+-------------------+-------------------+
| Field             | Type         | Null | Key | Default           | Extra             |
+-------------------+--------------+------+-----+-------------------+-------------------+
| code              | varchar(16)  | NO   | PRI | NULL              |                   |
| name              | varchar(255) | NO   |     | NULL              |                   |
| round_id          | int(11)      | NO   | MUL | NULL              |                   |
| puzzle_uri        | text         | NO   |     | NULL              |                   |
| ismeta            | tinyint(1)   | NO   |     | 0                 |                   |
| is_speculative    | tinyint(1)   | NO   |     | 0                 |                   |
| chat_channel_id   | varchar(255) | YES  |     | NULL              |                   |
| chat_channel_link | text         | YES  |     | NULL              |                   |
| drive_id          | varchar(255) | YES  |     | NULL              |                   |
| drive_uri         | text         | YES  |     | NULL              |                   |
| created_at        | timestamp    | NO   |     | CURRENT_TIMESTAMP | DEFAULT_GENERATED |
+-------------------+--------------+------+-----+-------------------+-------------------+
```

## Rollback (if needed)

To remove the table if there's an issue:
```sql
DROP TABLE IF EXISTS temp_puzzle_creation;
```

**Note:** This table is ephemeral - rows are deleted after puzzle creation completes. Dropping it will only affect in-progress puzzle creations.

### Integer ID Enforcement (JSON_TABLE + normalize_solver_ids)

This migration has two parts: a SQL function rewrite and a data normalization.
Run them **in order** after deploying the updated code.

**Step 1: Deploy code** (git pull, restart gunicorn)

The new Python code normalizes all IDs to `int()` at function boundaries and
uses `JSON_TABLE` queries instead of `JSON_SEARCH`/`JSON_CONTAINS`. It is
backwards-compatible with both int and string solver_ids in existing data,
so deploying first is safe.

**Step 2: Rewrite SQL functions**

```bash
mysql -u puzzleboss -p puzzleboss < scripts/migrations/rewrite_json_search_to_json_table.sql
```

What it does:
- Rewrites `get_current_puzzle()` and `get_all_puzzles()` from `JSON_SEARCH` to `JSON_TABLE` with `INT PATH`
- `JSON_TABLE` handles both int and string JSON values via coercion, so this is safe before or after data normalization
- Safe to re-run (uses `DROP FUNCTION IF EXISTS`)

Verify:
```sql
-- Should return puzzle name if solver 101 is assigned, or '' if not
SELECT get_current_puzzle(101);
SELECT get_all_puzzles(101);
```

**Step 3: Normalize JSON data**

```bash
curl -X POST http://localhost:5000/migrate/normalize_solver_ids
```

What it does:
- Scans all puzzles with `current_solvers` or `solver_history` JSON columns
- Converts any string solver_ids (`"101"`) to integers (`101`)
- Idempotent: int values are left as-is, safe to re-run

Expected response:
```json
{"status": "ok", "message": "Normalized 3 puzzle(s) out of 15 total"}
```

**Rollback:** Not needed — `JSON_TABLE` with `INT PATH` handles both int and string
values, so the SQL functions work regardless of data state. The Python code also
handles both types via `int()` normalization.

---

## General Migration Guidelines

1. Always backup the database before running migrations:
   ```bash
   mysqldump -u puzzleboss -p puzzleboss > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. Test migrations in a staging environment first

3. Run migrations during low-traffic periods when possible

4. Monitor application logs after deployment

5. Keep migrations idempotent (safe to run multiple times)
