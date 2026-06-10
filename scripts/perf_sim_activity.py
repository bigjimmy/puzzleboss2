#!/usr/bin/env python3
"""Seed prod-shaped data at a given scale and benchmark the activity-heavy
query paths. For local perf analysis only — do not run against prod.

Replicates the January 2026 hunt data shape observed in production:
  - 275 puzzles, 18 rounds, 263 solvers
  - ~30K activity rows at scale=1, power-law distributed per puzzle
    (max ~1165, avg ~104), 86% 'revise' / 11% 'interact'
  - ~90% of puzzles solved (activity stops partway through the hunt window)

Usage (inside the app container):
  python /app/scripts/perf_sim_activity.py seed --scale 1
  python /app/scripts/perf_sim_activity.py bench
  python /app/scripts/perf_sim_activity.py bench --with-index
"""

import argparse
import json
import math
import random
import time
from datetime import datetime, timedelta

import MySQLdb
import yaml

HUNT_START = datetime(2026, 1, 16, 18, 0, 0)
HUNT_HOURS = 72
N_PUZZLES = 275
N_ROUNDS = 18
N_SOLVERS = 263

TYPE_WEIGHTS = [
    ("revise", 0.863),
    ("interact", 0.114),
    ("comment", 0.010),
    ("create", 0.008),
    ("solve", 0.005),
]

STATUSES_SOLVED_FRACTION = 0.90


def connect():
    with open("/app/puzzleboss.yaml") as f:
        cfg = yaml.safe_load(f)["MYSQL"]
    return MySQLdb.connect(
        host=cfg["HOST"],
        user=cfg["USERNAME"],
        passwd=cfg["PASSWORD"],
        db=cfg["DATABASE"],
        charset="utf8mb4",
    )


def pick_type(rng):
    r = rng.random()
    acc = 0.0
    for name, w in TYPE_WEIGHTS:
        acc += w
        if r < acc:
            return name
    return "revise"


def seed(scale):
    rng = random.Random(42)
    db = connect()
    cur = db.cursor()

    print(f"Wiping and reseeding at scale={scale}x ...")
    for table in ("activity", "puzzle", "round", "solver"):
        cur.execute(f"DELETE FROM {table}")
    db.commit()

    cur.executemany(
        "INSERT INTO solver (id, name, fullname) VALUES (%s, %s, %s)",
        [(i, f"solver{i}", f"Solver Number{i}") for i in range(1, N_SOLVERS + 1)],
    )
    cur.executemany(
        "INSERT INTO round (id, name, status) VALUES (%s, %s, 'Being worked')",
        [(i, f"Round {i}") for i in range(1, N_ROUNDS + 1)],
    )

    # Per-puzzle activity counts: power law matching prod (max 1165, avg ~104)
    base_counts = [max(4, int(1165 * (rank + 1) ** -0.6)) for rank in range(N_PUZZLES)]
    rng.shuffle(base_counts)
    print(f"  base activity rows at 1x: {sum(base_counts)}")

    puzzles = []
    for pid in range(1, N_PUZZLES + 1):
        solved = rng.random() < STATUSES_SOLVED_FRACTION
        nsolvers = rng.randint(1, 8)
        sids = rng.sample(range(1, N_SOLVERS + 1), nsolvers)
        history = json.dumps({"solvers": [{"solver_id": s} for s in sids]})
        current = json.dumps({"solvers": [{"solver_id": s} for s in sids[:2]]}) if not solved else None
        puzzles.append(
            (
                pid,
                f"Puzzle {pid}",
                "Solved" if solved else "Being worked",
                "ANSWER%d" % pid if solved else None,
                (pid - 1) % N_ROUNDS + 1,
                f"https://example.com/puzzle/{pid}",
                f"https://docs.google.com/spreadsheets/d/fake{pid}",
                current,
                history,
                rng.randint(1, 50),
            )
        )
    cur.executemany(
        """INSERT INTO puzzle (id, name, status, answer, round_id, puzzle_uri,
           drive_uri, current_solvers, solver_history, sheetcount)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        puzzles,
    )
    db.commit()

    rows = []
    total = 0
    t0 = time.time()
    for pid in range(1, N_PUZZLES + 1):
        count = base_counts[pid - 1] * scale
        # Solved puzzles stop getting activity partway through the hunt;
        # this reproduces the "heavy puzzle whose lastact is old" case that
        # punishes a backward time-index scan.
        end_frac = rng.uniform(0.15, 1.0)
        window = HUNT_HOURS * 3600 * end_frac
        times = sorted(rng.uniform(0, window) for _ in range(count))
        for ts in times:
            rows.append(
                (
                    HUNT_START + timedelta(seconds=ts),
                    rng.randint(1, N_SOLVERS),
                    pid,
                    "bigjimmybot" if rng.random() < 0.9 else "puzzleboss",
                    pick_type(rng),
                    f"https://docs.google.com/spreadsheets/d/fake{pid}/edit#rev={int(ts)}",
                )
            )
        if len(rows) >= 20000:
            cur.executemany(
                "INSERT INTO activity (time, solver_id, puzzle_id, source, type, uri)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                rows,
            )
            db.commit()
            total += len(rows)
            print(f"  inserted {total} rows ({time.time()-t0:.1f}s)")
            rows = []
    if rows:
        cur.executemany(
            "INSERT INTO activity (time, solver_id, puzzle_id, source, type, uri)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            rows,
        )
        db.commit()
        total += len(rows)
    cur.execute("ANALYZE TABLE activity")
    print(f"Done: {total} activity rows in {time.time()-t0:.1f}s")


def timeq(cur, label, sql, args=(), n=5):
    # warm once, then take best-of-n (steady-state buffer pool)
    cur.execute(sql, args)
    cur.fetchall()
    best = math.inf
    for _ in range(n):
        t0 = time.perf_counter()
        cur.execute(sql, args)
        cur.fetchall()
        best = min(best, time.perf_counter() - t0)
    print(f"  {label}: {best*1000:.1f}ms")
    return best


LASTACTCACHED_SQL = """
SELECT a.* FROM activity a
INNER JOIN (
    SELECT puzzle_id, MAX(time) AS max_time
    FROM activity GROUP BY puzzle_id
) latest ON a.puzzle_id = latest.puzzle_id AND a.time = latest.max_time
ORDER BY a.id DESC
"""

LASTACT_SQL = "SELECT * FROM activity WHERE puzzle_id = %s ORDER BY time DESC, id DESC LIMIT 1"


def bench(with_index):
    db = connect()
    cur = db.cursor()

    cur.execute("SELECT COUNT(*) FROM activity")
    nact = cur.fetchone()[0]

    if with_index:
        cur.execute("SHOW INDEX FROM activity WHERE Key_name = 'idx_puzzle_time'")
        if not cur.fetchall():
            print("Adding composite index (puzzle_id, time) ...")
            t0 = time.time()
            cur.execute("ALTER TABLE activity ADD INDEX idx_puzzle_time (puzzle_id, time)")
            print(f"  index built in {time.time()-t0:.1f}s")
    else:
        cur.execute("SHOW INDEX FROM activity WHERE Key_name = 'idx_puzzle_time'")
        if cur.fetchall():
            cur.execute("ALTER TABLE activity DROP INDEX idx_puzzle_time")

    # heaviest puzzle, and a heavy puzzle whose last activity is oldest
    cur.execute(
        "SELECT puzzle_id, COUNT(*) c, MAX(time) mt FROM activity GROUP BY puzzle_id ORDER BY c DESC LIMIT 1"
    )
    heavy_pid, heavy_n, _ = cur.fetchone()
    cur.execute(
        """SELECT puzzle_id, COUNT(*) c, MAX(time) mt FROM activity
           GROUP BY puzzle_id HAVING c > 100 ORDER BY mt ASC LIMIT 1"""
    )
    old_pid, old_n, old_mt = cur.fetchone()
    cur.execute("SELECT puzzle_id, COUNT(*) c FROM activity GROUP BY puzzle_id ORDER BY c ASC LIMIT 1")
    light_pid, light_n = cur.fetchone()

    print(f"\n=== bench: {nact} activity rows, index={'YES' if with_index else 'no'} ===")
    timeq(cur, f"lastactcached GROUP BY join (the /all rebuild query)", LASTACTCACHED_SQL)
    timeq(cur, f"lastact heavy puzzle {heavy_pid} ({heavy_n} acts)", LASTACT_SQL, (heavy_pid,))
    timeq(cur, f"lastact heavy+old puzzle {old_pid} ({old_n} acts, last={old_mt})", LASTACT_SQL, (old_pid,))
    timeq(cur, f"lastact light puzzle {light_pid} ({light_n} acts)", LASTACT_SQL, (light_pid,))
    timeq(cur, "full /activity dump (SELECT * FROM activity)", "SELECT * FROM activity", n=3)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed")
    s.add_argument("--scale", type=int, default=1)
    b = sub.add_parser("bench")
    b.add_argument("--with-index", action="store_true")
    args = ap.parse_args()
    if args.cmd == "seed":
        seed(args.scale)
    else:
        bench(args.with_index)
