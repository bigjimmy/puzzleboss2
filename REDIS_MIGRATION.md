# Redis Migration Plan — puzzleboss2 (App Side)

> **Status (June 2026):** Phases A / 0 / 1 / 2 / 3 / 4 are **COMPLETE and live in
> production.** Redis is the active cache backend; REDIS_ENABLED is true in prod;
> write-through lastact is deployed; the Phases 0–3 and Phase 4 checklists below
> are fully checked off. The only remaining work is **Phase 4-infra** (removing the
> now-idle memcache ECS service — memcache still runs in the cluster but nothing
> connects to it).

This document covers the app-side changes for migrating from memcache to Redis,
plus the performance work that motivates it: serving fresh per-puzzle `lastact`
inside `/all` without the invalidation churn that design would otherwise cause.
See `puzzleboss2-infra/REDIS_MIGRATION.md` for the infrastructure side.

Phases:

- **Phase A — activity composite index.** Standalone, deployable immediately,
  no Redis dependency. Do this first.
- **Phases 0–3 — the backend swap** (memcache → Redis, like-for-like).
- **Phase 4 — write-through lastact.** The payoff: fresh `lastact` in every
  `/all` response with near-zero invalidations. Requires Redis.

## Background

Memcache serves two purposes in this system:
1. **OIDC session storage** via `mod_auth_openidc` (`OIDCCacheType memcache`) — used by both
   the puzzleboss and mediawiki containers. Hard failure mode: users get 401/400 if unavailable.
2. **API response cache** for the `/all` endpoint via `pbcachelib.py` (`/allcached` is a
   deprecated alias kept for backwards compatibility — same code path). Soft failure mode:
   cache miss falls through to DB query, higher latency but no outage.

Both containers share the same cache backend so OIDC sessions are portable across ALB routing
(a user hitting `/pb/*` and `/wiki/*` stays logged in without re-auth).

`mod_auth_openidc` on Debian supports `OIDCCacheType redis` natively (hiredis compiled in).
The public API of `pbcachelib.py` (`cache_get`, `cache_set`, `cache_delete`,
`invalidate_all_cache`) is unchanged by the swap — only the internals change.

### Performance findings (June 2026, prod + local simulation)

Measured against January 2026 hunt data (30.7K activity rows, 275 puzzles,
86% bigjimmybot `revise`) and a local simulation reseeded at 4x/16x scale
(`scripts/perf_sim_activity.py`):

| Quantity | Value |
|---|---|
| Peak activity write rate (hunt) | 22.5/min — one every **2.7s** (p90 every 4s) |
| `/all` poll rate | 5s per client (`index.php`) → ~8–10 req/s at 40–50 solvers |
| Cache invalidations (lifetime counter) | **31.8K** — all from REST mutations (puzzle PATCHes invalidate unconditionally for *any* part, plus round/hint/create/delete ops). Hunt-time volume was only ~4–5K (~1/min: UI edits logged as legacy `interact` + creates/solves/comments); the counter is likely dominated by load testing |
| `/all` rebuild, 30K rows | ~20ms |
| `/all` rebuild, 400K rows (16x), current indexes | **272ms** |
| `/all` rebuild, 400K rows, with `(puzzle_id, time)` index | **27ms** |
| `lastactcached` GROUP BY alone, 25K → 400K rows | 12ms → 240ms (O(total activity)); **1.1ms flat** with the index |
| Per-puzzle lastact, puzzle with old last activity, 400K rows | 184ms (backward `time`-index scan); **0.1ms** with the index |

Two structural conclusions:

1. **Today's invalidation rate is low** (~1/min during the hunt — human
   actions through the UI, which hit the unconditional PATCH invalidation
   regardless of which field changed). Serving *fresh* lastact by invalidating on every
   activity write would raise that ~10x to the activity write rate (peak one
   per 2.7s) — and at the same time the rebuild each miss pays grows with
   activity volume (272ms at 16x, unindexed) and stampedes (2–3 concurrent
   misses per invalidation, no lock). That combination is what Phase 4 avoids.
2. **Invalidation-based caching couples write frequency to read cost.** Putting
   fresh lastact into `/all` by invalidating on every activity write forces
   readers to redo O(everything) per write. Write-through (Phase 4) decouples
   them: each write does O(1) work for the thing that changed.

## Phase A — activity composite index (do this now)

Standalone commit, deployable to prod immediately, independent of all Redis work.

- `scripts/puzzleboss.sql`: add `KEY idx_puzzle_time (puzzle_id, time)` to `activity`
- `migrations/add_activity_puzzle_time_index.py`: idempotent prod migration
  (`POST /migrate/add_activity_puzzle_time_index`; online DDL, doesn't block traffic)

What it fixes, regardless of cache backend:

- The `lastactcached` GROUP BY becomes a loose index scan — cost scales with
  puzzle count (~275 groups), not activity count. `/all` rebuild stays ~27ms
  even at 16x activity volume.
- `get_last_activity_for_puzzle` stops falling into the backward `time`-index
  scan trap (the optimizer walks the whole table backwards for puzzles whose
  last activity is old — exactly the late-hunt steady state).
- It is the safety net under every Phase 4 fallback path: cold start, Redis
  flush, cache disabled. With the index, the worst case is always ~27ms.

## Files to change (backend swap, Phases 0–1)

### `requirements.txt`
- Remove `pymemcache`
- Add `redis`

### `pbcachelib.py`
- Swap `from pymemcache.client import base as memcache_client` → `import redis`
- `init_memcache(configstruct)` reads `REDIS_ENABLED`, `REDIS_HOST`, `REDIS_PORT` from config
- Client init:
  ```python
  redis.Redis(host=host, port=port, decode_responses=True,
              socket_timeout=1, socket_connect_timeout=1)
  ```
- `cache_get(key)`: `r.get(key)` (returns string with decode_responses=True, or None)
- `cache_set(key, value, ttl)`: `r.set(key, value, ex=ttl)`
- `cache_delete(key)`: `r.delete(key)`
- Rename `ensure_memcache_initialized` → `ensure_cache_initialized`
- Update DB query to read `REDIS_%` config keys instead of `MEMCACHE_%`
- Module-level constants: `MEMCACHE_AVAILABLE` → `REDIS_AVAILABLE`, keep `CACHE_KEY`/`CACHE_TTL`

### `docker/prod/apache-prod.conf` (lines 40-41)
```apache
OIDCCacheType            redis
OIDCRedisCacheServer     "redis.puzzleboss.local:6379"
```
Remove `OIDCMemCacheServers` line.

### `puzzleboss2-infra/docker/mediawiki/apache-mediawiki.conf` (lines 44-45)
```apache
OIDCCacheType            redis
OIDCRedisCacheServer     "redis.puzzleboss.local:6379"
```
Remove `OIDCMemCacheServers` line.

### `www/config.php` (lines 431-433, 483-485)
- Config group label: "Memcache" → "Redis"
- Keys: `MEMCACHE_ENABLED` → `REDIS_ENABLED`, `MEMCACHE_HOST` → `REDIS_HOST`, `MEMCACHE_PORT` → `REDIS_PORT`
- Descriptions: update accordingly

### `migrations/rename_cache_config_keys.py` (new file)
New idempotent migration:
- Name: `rename_cache_config_keys`
- Description: Renames MEMCACHE_ENABLED/HOST/PORT → REDIS_ENABLED/HOST/PORT in config table
- Logic: for each old key, if old key exists AND new key does not exist, rename it; skip otherwise

### `docker-compose.yml` (Phase 0 — dev environment)
- Add `redis:7-alpine` service on port 6379
- Update app service environment to seed `REDIS_ENABLED=true`, `REDIS_HOST=redis`, `REDIS_PORT=6379`
  (or update the DB init SQL to insert these config rows)

## Rollout sequence

> **Historical — all phases below are complete.** Preserved for reference.

This repo's changes are **Phase 0** (dev) and **Phase 1** (app code commit) in the overall plan.
~~Do NOT deploy Phase 1 until Phase 2 (infra: Redis ECS service up) is complete.~~
Phase A (index) deploys ahead of everything.

### Phase 0 — Local dev
1. Update docker-compose.yml to add redis service
2. `docker-compose up --build`
3. Verify `/all` returns data and Redis has the key
4. Run unit tests: `python3 -m pytest tests/ -v`
5. Run API tests: `docker exec puzzleboss-app python /app/scripts/test_api_coverage.py --allow-destructive`

### Phase 1 — Commit (do not deploy yet)
All changes above in a single commit:
```
Migrate cache layer from memcache to Redis

- pbcachelib.py: swap pymemcache → redis-py, read REDIS_* config keys
- Apache configs: OIDCCacheType redis + OIDCRedisCacheServer for both containers
- www/config.php: rename MEMCACHE_* → REDIS_* config keys and labels
- migrations/: add rename_cache_config_keys migration
- requirements.txt: pymemcache → redis
```

### Phase 3 — Cutover (after infra Phase 2 confirms Redis is up)
1. `POST /migrate/rename_cache_config_keys` — rename config table keys
2. Deploy new images for BOTH puzzleboss and mediawiki containers simultaneously
   (split deployment causes cross-container session mismatch)
3. Verify:
   - Fresh Google SSO login succeeds
   - `/pb/` and `/wiki/` both work without re-auth (shared Redis session)
   - `/all` returns data; second request shows cache hit in logs
   - `redis-cli -h redis.puzzleboss.local keys '*'` shows `puzzleboss:all`

**Note:** All users will be logged out once during cutover — OIDC sessions in memcache
cannot be migrated to Redis. Plan for off-hours.

## Phase 4 — write-through lastact (the motivation)

Goal: every `/all` response carries the *current* last activity for every
puzzle, without invalidating the blob on activity writes. The backend swap
(Phases 0–3) is the prerequisite; this phase is why Redis specifically.

### Data design

One Redis hash alongside the blob key:

| Key | Type | Contents |
|---|---|---|
| `puzzleboss:all` | string | the `/all` JSON blob (as today), structural data only |
| `puzzleboss:lastact` | hash | field = puzzle id, value = JSON activity row (`time` as ISO 8601, same shape as `_serialize_activity_for_cache`) |

No TTL on the hash — it's write-through, never stale, updated in place.

### Write path

`pblib.log_activity()` is the single chokepoint for **all** activity inserts —
pbrest and bigjimmybot both go through it. After the DB commit:

```python
# in log_activity, after conn.commit()
cache_hset("puzzleboss:lastact", str(puzzle_id), json.dumps(serialized_row))
```

- New `pbcachelib` helpers: `cache_hset(key, field, value)`,
  `cache_hgetall(key)` — same fail-silent convention as the existing ops.
- HSET after commit, never before: the hash may briefly *trail* the DB
  (fail-safe), never lead it.
- A failed HSET leaves that puzzle's entry stale until its next activity.
  Acceptable: the reader-side fallback (below) self-heals on blob rebuilds.

### Read path (`/all` serving)

```python
blob = cache_get(CACHE_KEY)            # structural data, as today
lastact = cache_hgetall(LASTACT_KEY)   # ~0.5ms for 275 fields
# attach and serve
```

Measured serving cost of attaching lastact to a 186KB cached blob:

- Graft into each puzzle dict (`loads` → set `lastactcached` per puzzle →
  `dumps`): **1.2ms**. Keeps the response shape identical — consumers keep
  reading `puzzle.lastactcached`.
- Alternative: append as a sibling top-level key (`"lastact": {pid: {...}}`)
  by string concatenation: **0.2ms**, but changes the response contract.

Start with the graft (zero consumer changes); revisit only if profiling says so.

> **Implementation note:** On deployment the per-puzzle field was named `lastact`
> (not `lastactcached` as the design draft above used). `lastactcached` is retired
> from API responses, Swagger specs, and tests. The design text above is preserved
> for historical context; the live field name and the key used in the Redis hash is
> `lastact`.

On rebuild (blob miss), `_get_all_from_db()` drops its GROUP BY query and
instead reads the hash; any puzzle missing from the hash falls back to the
indexed GROUP BY (~1.1ms thanks to Phase A) and backfills the hash. This is
also the cold-start path after a Redis flush.

`get_one_puzzle` / `get_puzzle_part(lastact)` can read the hash first and fall
back to the DB — eliminates the worst per-puzzle latency (~92ms observed in
prod), though these endpoints are nearly unused (the UI rides `/all`).

### Invalidation allowlist

With lastact decoupled, blob invalidation must become an explicit allowlist —
**only structural changes**: puzzle create/delete, round create/delete/update,
puzzle status transitions.

Two unconditional invalidation paths must become selective:

- The REST PATCH/POST puzzle-part handlers (`update_puzzle_parts`,
  `update_puzzle_part` in pbrest.py) invalidate for *any* part — including
  `lastact`, which is a pure activity-row INSERT that never touches the
  puzzle row. **Done (interim, June 2026):** the handlers now skip
  invalidation for `lastact`-only updates. No production caller POSTs
  `lastact` today (puzzcord's `post_puzzle_parts` helper has no callers;
  only loadtest.py and the API test suite hit it), but it's the endpoint
  any future activity-writer would use. Still to do here: `xyzloc` /
  `comments` — TTL staleness is fine for those too.
- `update_puzzle_field` (pblib.py) invalidates on every field update by
  invariant ("any puzzle mutation"). Its bigjimmybot-driven writes are
  low-frequency (`sheetcount` is the spreadsheet's *tab count* — it changes
  on tab add/delete, not on edits; `sheetenabled` is once per puzzle), so
  this path is not a hot source today, but it should adopt the same
  allowlist so a future high-churn field doesn't silently recreate the
  problem.

Expected effect: invalidations drop from "every puzzle mutation" to a few
hundred structural events per hunt, and — critically — adding fresh lastact
to `/all` adds zero invalidations instead of coupling the blob's lifetime to
the activity write rate (peak: one write per 2.7s).

### Stampede lock

Concurrent misses currently all rebuild independently (2–3 wasted rebuilds per
invalidation at hunt-peak request rates). With Redis:

```python
if r.set("puzzleboss:all:lock", "1", nx=True, ex=5):
    rebuild_and_set()
else:
    serve_from_db_directly()  # or brief retry-loop on the cache key
```

Worst case under the lock is one rebuild per invalidation; with Phase A that's
~27ms even at 16x activity volume.

### Why memcache can't do this

275 independent keys with independent eviction (partial-data risk), no atomic
per-field update, no key enumeration, a 275-key `get_multi` per request, and
no persistence across restarts. Redis hashes + `SET NX` + RDB snapshots are
the natural fit.

### Phase 4 testing checklist
- [x] Activity insert (API + bigjimmybot paths) updates `puzzleboss:lastact` hash (`log_activity` write-through)
- [x] `/all` lastact matches latest activity row immediately after insert (no 15s lag) — attached per request
- [x] Blob invalidation fires ONLY on structural fields (`STRUCTURAL_PUZZLE_FIELDS` allowlist in `update_puzzle_field`)
- [x] `lastact` POST does NOT invalidate
- [x] `xyzloc` / `comments` / `sheetcount` updates do NOT invalidate (not in the allowlist)
- [x] Redis flush → next `/all` rebuilds blob and backfills hash from DB (indexed GROUP BY, `_get_lastact_map`)
- [x] Concurrent miss storm produces a single rebuild (`SET NX` lock in `_get_all_with_cache`)
- [x] `lastactcached` retired from API responses, swagger specs, and tests

**Deployed and live in production.** Branch `redis-lastact-writethrough` has been
merged. REDIS_ENABLED is true in prod; Redis is reachable at
`redis.puzzleboss.local:6379`. The remaining infra task is decommissioning the
now-idle memcache ECS service (nothing connects to it).

## Testing checklist (Phases 0–3)
- [x] `docker-compose up` works with Redis
- [x] `/all` endpoint caches and returns data
- [x] Cache invalidation fires on: puzzle delete, round create, round update
- [x] OIDC login works end-to-end (if testing in an environment with OIDC configured)
- [x] `python3 -m pytest tests/ -v` passes
- [x] API integration tests pass in Docker
