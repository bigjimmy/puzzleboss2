# Puzzleboss 2000 — ECS Operations Guide

This document covers day-to-day operations for the production ECS Fargate deployment.

For the infrastructure design rationale and Terraform structure, see [terraform/INFRASTRUCTURE_PLAN.md](terraform/INFRASTRUCTURE_PLAN.md).

## Architecture Overview

```
Route 53 (importanthuntpoll.org) → ALB (ACM cert, HTTPS)
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
    /pb*, /account*,            / (default),              /metrics* →
    /apidocs*, /health          /wiki*                    /phpmyadmin*, /scripts*,
         │                           │                    /mailmanarchives*
         ▼                           ▼                         ▼
   ECS: puzzleboss            ECS: mediawiki            EC2: observability
   (1 vCPU / 3 GB)           (0.5 vCPU / 1 GB)         (t4g.small)
   Apache+PHP+Gunicorn        Apache+PHP+MediaWiki 1.43  Prometheus+Loki+Grafana
         │                           │                    Apache (legacy content)
         │         ┌─────────────────┤
         ▼         ▼                 ▼
   ECS: memcache        ECS: bigjimmy         AWS RDS MySQL
   (0.25 vCPU/512MB)   (0.25 vCPU/512MB)     (db.t4g.small)
   OIDC sessions +      Sheet activity
   puzzle cache          polling bot
```

All ECS tasks run on **ARM64/Graviton** (Fargate) with **Fluent Bit** sidecars routing logs to Loki.

## Deploying Code Changes

### Quick Deploy (Recommended)

Use the helper script from the repo root:

```bash
# Deploy everything (puzzleboss + bigjimmy + mediawiki)
./deploy-ecs.sh

# Deploy only one service
./deploy-ecs.sh --service puzzleboss
./deploy-ecs.sh --service bigjimmy
./deploy-ecs.sh --service mediawiki

# Build and push images without restarting services
./deploy-ecs.sh --build-only
```

### Manual Deploy Steps

If you need more control, or `deploy-ecs.sh` doesn't suit your needs:

```bash
# 1. Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 497640181477.dkr.ecr.us-east-1.amazonaws.com

# 2. Build for ARM64 (Graviton)
docker build --platform linux/arm64 \
  -t 497640181477.dkr.ecr.us-east-1.amazonaws.com/puzzleboss/puzzleboss:latest \
  -f Dockerfile.prod .

# 3. Push
docker push 497640181477.dkr.ecr.us-east-1.amazonaws.com/puzzleboss/puzzleboss:latest

# 4. Register a new task definition revision (re-resolves :latest digest)
aws ecs describe-task-definition --task-definition puzzleboss-web \
  --query 'taskDefinition.{family:family,taskRoleArn:taskRoleArn,executionRoleArn:executionRoleArn,networkMode:networkMode,containerDefinitions:containerDefinitions,volumes:volumes,requiresCompatibilities:requiresCompatibilities,cpu:cpu,memory:memory,runtimePlatform:runtimePlatform}' \
  --output json > /tmp/taskdef.json

aws ecs register-task-definition --cli-input-json file:///tmp/taskdef.json

# 5. Update the service with the new revision
aws ecs update-service --cluster puzzleboss --service puzzleboss \
  --task-definition puzzleboss-web:<NEW_REVISION> --force-new-deployment

# 6. Monitor deployment
aws ecs wait services-stable --cluster puzzleboss --services puzzleboss
```

### Important: Task Definition Revisions

> **Gotcha:** ECS task definitions are immutable. The `:latest` tag is resolved to a
> specific image digest at task definition registration time. Running
> `--force-new-deployment` alone will **re-use the cached digest** — it does NOT
> re-pull `:latest`. You **must register a new task definition revision** after
> pushing a new image, then update the service to use that revision.

### Service ↔ Task Definition Mapping

| ECS Service | Task Definition Family | Docker Image | Notes |
|-------------|----------------------|--------------|-------|
| `puzzleboss` | `puzzleboss-web` | `puzzleboss/puzzleboss:latest` | Web tier (Apache + Gunicorn) |
| `bigjimmy` | `puzzleboss-bigjimmy` | `puzzleboss/puzzleboss:latest` | Same image, different entrypoint |
| `mediawiki` | `puzzleboss-mediawiki` | `puzzleboss/mediawiki:latest` | Separate image |
| `memcache` | `puzzleboss-memcache` | `memcached:1.6-alpine` | Public image, no build needed |

Since **puzzleboss** and **bigjimmy** share the same Docker image, a code change requires deploying both:

```bash
# After pushing puzzleboss image, register new revisions for BOTH
aws ecs register-task-definition --cli-input-json file:///tmp/pb-taskdef.json
aws ecs register-task-definition --cli-input-json file:///tmp/bj-taskdef.json
aws ecs update-service --cluster puzzleboss --service puzzleboss --task-definition puzzleboss-web:<REV>
aws ecs update-service --cluster puzzleboss --service bigjimmy --task-definition puzzleboss-bigjimmy:<REV>
```

### Verifying a Deployment

```bash
# Check all services are 1/1 running with 1 deployment each
aws ecs describe-services --cluster puzzleboss \
  --services puzzleboss mediawiki bigjimmy memcache \
  --query 'services[].{name:serviceName,running:runningCount,desired:desiredCount,deployments:length(deployments)}' \
  --output table

# Smoke test endpoints
curl -sk https://importanthuntpoll.org/health        # → "OK"
curl -sk -o /dev/null -w '%{http_code}' https://importanthuntpoll.org/pb/   # → 302 (OIDC)
curl -sk -o /dev/null -w '%{http_code}' https://importanthuntpoll.org/      # → 302 (OIDC)
```

## Scaling for Hunt

Edit `terraform/terraform.tfvars` and apply:

```hcl
# Scale up for January hunt
puzzleboss_desired_count = 2       # 1 → 2 web tasks
bigjimmy_cpu             = 512     # 256 → 512
bigjimmy_memory          = 1024    # 512 → 1024
```

```bash
cd terraform && terraform apply
```

Scale back down after hunt by reverting the values.

## Secrets Management

All secrets are stored in **AWS Secrets Manager** and injected as environment variables at container startup. The entrypoint scripts decode base64-encoded file secrets to disk.

| Secret | Containers | Format | Purpose |
|--------|-----------|--------|---------|
| `puzzleboss/oidc-client-id` | puzzleboss, mediawiki | plain string | Google OAuth client ID |
| `puzzleboss/oidc-client-secret` | puzzleboss, mediawiki | plain string | Google OAuth client secret |
| `puzzleboss/oidc-crypto-passphrase` | puzzleboss, mediawiki | plain string | OIDC session encryption key (shared across containers) |
| `puzzleboss/puzzleboss-yaml` | puzzleboss, bigjimmy | base64 file | Database config (`puzzleboss.yaml`) |
| `puzzleboss/google-sa-json` | puzzleboss, bigjimmy | base64 file | Google service account key |
| `puzzleboss/mediawiki-localsettings` | mediawiki | base64 file | MediaWiki `LocalSettings.php` |

### Updating a Secret

```bash
# String secret
aws secretsmanager put-secret-value \
  --secret-id puzzleboss/oidc-client-id \
  --secret-string "NEW_VALUE"

# File secret (base64-encode the file)
aws secretsmanager put-secret-value \
  --secret-id puzzleboss/puzzleboss-yaml \
  --secret-string "$(base64 < puzzleboss.yaml)"

# After updating secrets, restart the affected service to pick up new values
aws ecs update-service --cluster puzzleboss --service puzzleboss --force-new-deployment
```

> **Note:** Secret changes require a service restart. ECS pulls secrets at task launch time, not continuously.

## Monitoring & Observability

### Endpoints

| Service | URL | Auth |
|---------|-----|------|
| Grafana | `https://importanthuntpoll.org/metrics/` | ALB OIDC (Google Workspace) |
| Prometheus | `http://<observability-private-ip>:9090` | VPC only |
| Loki | `http://<observability-private-ip>:3100` | VPC only |

### Checking Logs via Loki

SSH to the observability instance and query Loki directly:

```bash
# SSH to observability (non-standard port 3748)
ssh -i ~/.ssh/mysteryhunt.pem -p 3748 ubuntu@<observability-eip>

# Query recent logs for a service
curl -sG "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={service="puzzleboss"}' \
  --data-urlencode "limit=20" \
  --data-urlencode "start=$(date -d '10 minutes ago' +%s)000000000" \
  --data-urlencode "end=$(date +%s)000000000" | python3 -m json.tool

# Filter for errors
curl -sG "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={service="mediawiki"} |~ "error|Error"' \
  --data-urlencode "limit=20" \
  --data-urlencode "start=$(date -d '10 minutes ago' +%s)000000000" \
  --data-urlencode "end=$(date +%s)000000000" | python3 -m json.tool
```

Available `service` labels: `puzzleboss`, `mediawiki`, `bigjimmy`, `memcache`.

### Prometheus Metrics

Prometheus scrapes two endpoints from the puzzleboss container:
- **Port 5000** (`puzzleboss_api` job): Flask/Gunicorn metrics via `prometheus_flask_exporter`
- **Port 80** (`puzzleboss_app` job): PHP hunt metrics at `/pb/metrics.php` (puzzles, solves, activity, botstats)

Discovery is automatic via Prometheus's native `aws_sd_configs` (ECS service discovery).

## Database Operations

### Connecting to RDS

```bash
# From the observability instance (has MySQL client)
ssh -i ~/.ssh/mysteryhunt.pem -p 3748 ubuntu@<observability-eip>
mysql -h wind-up-birds.cok5fns5quqc.us-east-1.rds.amazonaws.com -u bigjimmy -p puzzleboss2

# Or via phpMyAdmin (OIDC-protected)
https://importanthuntpoll.org/phpmyadmin/
```

### Runtime Configuration

Many settings are stored in the `config` table and auto-refresh every 30 seconds:

```sql
-- View all config
SELECT `key`, val FROM config;

-- Update a setting (takes effect within 30 seconds)
UPDATE config SET val='new_value' WHERE `key`='SETTING_NAME';
```

Key runtime settings: `MEMCACHE_HOST`, `MEMCACHE_ENABLED`, `LOGLEVEL`, `SKIP_PUZZCORD`, `SKIP_GOOGLE_API`, `BIGJIMMY_PUZZLEPAUSETIME`.

### Reset Hunt for New Event

```bash
# Preserves solver accounts, wipes puzzles/rounds/activity
# Run from within a container or locally with DB access
python scripts/reset-hunt.py
```

### Run Data Migrations

```bash
# List available migrations
curl https://importanthuntpoll.org/pb/apicall.php?apicall=migrate  # (requires auth)

# Or via the REST API directly from within the VPC
curl http://<puzzleboss-task-ip>:5000/migrate
curl -X POST http://<puzzleboss-task-ip>:5000/migrate/<migration_name>
```

## Infrastructure Changes (Terraform)

```bash
cd terraform

# Preview changes
terraform plan

# Apply changes
terraform apply

# Show current outputs (ALB DNS, ECR URLs, etc.)
terraform output
```

> **Important:** ECS services have `lifecycle { ignore_changes = [task_definition] }` so that
> Terraform doesn't interfere with application deployments. Terraform manages the service
> configuration (scaling, networking) but not which task definition revision is running.

### Terraform State

State is stored in S3 with DynamoDB locking:
- **Bucket:** `puzzleboss-terraform-state` (us-east-1)
- **Lock table:** `puzzleboss-terraform-locks`

## ALB Routing Reference

| Priority | Path Pattern | Target | Auth |
|----------|-------------|--------|------|
| 10 | `/pb*`, `/apidocs*`, `/flasgger_static*`, `/apispec*`, `/oauth2callback` | puzzleboss | Container OIDC |
| 11 | `/account*`, `/register*`, `/health` | puzzleboss | None (public) |
| 15 | `/wiki*` | mediawiki | Container OIDC |
| 20 | `/metrics*` | grafana (observability:3000) | ALB OIDC |
| 30 | `/phpmyadmin*` | observability:80 | ALB OIDC |
| 40 | `/scripts*` | observability:80 | ALB OIDC |
| 50 | `/mailmanarchives*` | observability:80 | ALB OIDC |
| default | everything else (including `/`) | mediawiki | Container OIDC |

"Container OIDC" = Apache `mod_auth_openidc` inside the container.
"ALB OIDC" = ALB-level `authenticate-oidc` action (Google Workspace, restricted to team domain).

## OIDC Authentication

Both the Puzzleboss and MediaWiki containers use Apache `mod_auth_openidc` for Google Workspace SSO. The ALB also uses OIDC for Grafana and legacy web paths.

### Authorized Redirect URIs (Google Cloud Console)

These must be registered in the OAuth client (`APIs & Services → Credentials`):

- `https://importanthuntpoll.org/oauth2callback` — Puzzleboss mod_auth_openidc
- `https://importanthuntpoll.org/wiki/Special:OIDCCallback` — MediaWiki mod_auth_openidc
- `https://importanthuntpoll.org/oauth2/idpresponse` — ALB OIDC (Grafana, phpMyAdmin, scripts, mailman)

### Session Storage

OIDC sessions are stored in memcache (`memcache.puzzleboss.local:11211`). If memcache is unavailable, users will get 401/400 errors on login. The `OIDCCryptoPassphrase` is shared across all containers (from Secrets Manager) so sessions are portable.

> **After replacing containers:** Users may need to clear browser cookies for
> `importanthuntpoll.org` if they get "Bad Request" errors on OIDC callback.
> This happens when the state cookie references a session that was lost during
> container replacement.

## Troubleshooting

### "authenticated REMOTE_USER not provided"
The PHP page loaded without OIDC authentication. Check that the Apache `<Directory>` block has `AuthType openid-connect` / `Require valid-user` and does **not** also have `Require all granted` (which bypasses auth via Apache's implicit `RequireAny`).

### OIDC "Bad Request" or 400 on callback
Stale session cookie. User should clear cookies for `importanthuntpoll.org` and try again in a fresh browser tab.

### "redirect_uri_mismatch" from Google
The redirect URI isn't registered in Google Cloud Console. See the [Authorized Redirect URIs](#authorized-redirect-uris-google-cloud-console) section above.

### Memcache connection failures
Check that `MEMCACHE_HOST` in the database `config` table is set to `memcache.puzzleboss.local` (not the old EC2 hostname). Also verify the memcache ECS service is running: `aws ecs describe-services --cluster puzzleboss --services memcache`.

### ECS task keeps restarting
Check the stopped task's reason: `aws ecs describe-tasks --cluster puzzleboss --tasks <task-arn> --query 'tasks[].{reason:stoppedReason,containers:containers[].{name:name,reason:reason,exitCode:exitCode}}'`. Common causes: health check failure (check `/health` endpoint), secret not found (check Secrets Manager), or OOM (increase memory in `terraform.tfvars`).

### New image not picked up after deploy
You must register a new task definition revision. See [Important: Task Definition Revisions](#important-task-definition-revisions).

### MediaWiki extension incompatibility
The `mediawiki-aws-s3` extension is cloned from `master` (latest). If it bumps its minimum MediaWiki version, update `FROM mediawiki:X.YZ` in `Dockerfile.mediawiki` and the `Auth_remoteuser` branch to `REL1_YZ`.
