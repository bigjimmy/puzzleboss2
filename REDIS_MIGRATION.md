# Redis Migration Plan — puzzleboss2 (App Side)

This document covers the app-side changes for migrating from memcache to Redis.
See `puzzleboss2-infra/REDIS_MIGRATION.md` for the infrastructure side.

## Background

Memcache serves two purposes in this system:
1. **OIDC session storage** via `mod_auth_openidc` (`OIDCCacheType memcache`) — used by both
   the puzzleboss and mediawiki containers. Hard failure mode: users get 401/400 if unavailable.
2. **API response cache** for `/allcached` endpoint via `pbcachelib.py`. Soft failure mode:
   cache miss falls through to DB query, higher latency but no outage.

Both containers share the same cache backend so OIDC sessions are portable across ALB routing
(a user hitting `/pb/*` and `/wiki/*` stays logged in without re-auth).

`mod_auth_openidc` on Debian supports `OIDCCacheType redis` natively (hiredis compiled in).
The public API of `pbcachelib.py` (`cache_get`, `cache_set`, `cache_delete`,
`invalidate_all_cache`) is unchanged — only the internals swap.

## Files to change

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

### `docker/mediawiki/apache-mediawiki.conf` (lines 44-45)
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

This repo's changes are **Phase 0** (dev) and **Phase 1** (app code commit) in the overall plan.
Do NOT deploy Phase 1 until Phase 2 (infra: Redis ECS service up) is complete.

### Phase 0 — Local dev
1. Update docker-compose.yml to add redis service
2. `docker-compose up --build`
3. Verify `/allcached` returns data and Redis has the key
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
   - `/allcached` returns data; second request shows cache hit in logs
   - `redis-cli -h redis.puzzleboss.local keys '*'` shows `puzzleboss:all`

**Note:** All users will be logged out once during cutover — OIDC sessions in memcache
cannot be migrated to Redis. Plan for off-hours.

## Testing checklist
- [ ] `docker-compose up` works with Redis
- [ ] `/allcached` endpoint caches and returns data
- [ ] Cache invalidation fires on: puzzle delete, round create, round update
- [ ] OIDC login works end-to-end (if testing in an environment with OIDC configured)
- [ ] `python3 -m pytest tests/ -v` passes
- [ ] API integration tests pass in Docker
