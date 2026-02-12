"""
Normalize solver_id values in JSON columns to integers.

Background:
    solver.id is INT(11) in MySQL.  All SQL functions (get_current_solvers,
    get_all_solvers, get_current_puzzle, get_all_puzzles, puzzle_view) use
    JSON_TABLE with INT PATH to extract solver_ids, which handles both int
    and string values.  However, storing as int is correct because:

    1. It matches the native column type (solver.id INT)
    2. It matches how bigjimmybot passes solver_id (int from DictCursor)
    3. It matches how tags are stored in the tags JSON column ([42, 15, 8])
    4. JSON_TABLE INT PATH coerces both types, so int storage works everywhere

    Before this migration, some solver_ids may have been stored as strings
    (from Flask URL params via pbrest.py) or as ints (from bigjimmybot).
    This migration normalizes everything to int.

Idempotent: safe to re-run.  Int values are left as-is.
"""

import json

name = "normalize_solver_ids"
description = "Convert string solver_ids to ints in current_solvers and solver_history JSON columns"


def run(conn):
    """Normalize all solver_id values to integers. Returns (success, message)."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, current_solvers, solver_history FROM puzzle "
        "WHERE current_solvers IS NOT NULL OR solver_history IS NOT NULL"
    )
    rows = cursor.fetchall()

    updated = 0
    for row in rows:
        cs_changed = False
        sh_changed = False

        # Normalize current_solvers
        if row["current_solvers"]:
            cs = json.loads(row["current_solvers"])
            for s in cs.get("solvers", []):
                if not isinstance(s.get("solver_id"), int):
                    s["solver_id"] = int(s["solver_id"])
                    cs_changed = True
            if cs_changed:
                cursor.execute(
                    "UPDATE puzzle SET current_solvers = %s WHERE id = %s",
                    (json.dumps(cs), row["id"]),
                )

        # Normalize solver_history
        if row["solver_history"]:
            sh = json.loads(row["solver_history"])
            for s in sh.get("solvers", []):
                if not isinstance(s.get("solver_id"), int):
                    s["solver_id"] = int(s["solver_id"])
                    sh_changed = True
            if sh_changed:
                cursor.execute(
                    "UPDATE puzzle SET solver_history = %s WHERE id = %s",
                    (json.dumps(sh), row["id"]),
                )

        if cs_changed or sh_changed:
            updated += 1

    conn.commit()
    return True, f"Normalized {updated} puzzle(s) out of {len(rows)} total"
