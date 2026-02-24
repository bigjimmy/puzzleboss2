# Puzzleboss 2000 — Infrastructure Migration Plan

## Overview

Migration from hand-configured EC2 instances to containerized ECS Fargate deployment,
fully managed via Terraform. Goal: reproducibility, containerization, and the ability
to tear down and rebuild the entire stack from code.

## Current Architecture

- **2x t3.medium EC2** (ASG + ALB): Apache + PHP + Gunicorn (8 workers) + Puzzleboss
- **1x t3.medium EC2** ("series-of-tubes"): BigJimmy bot + Memcache + Prometheus + Loki + Grafana + NFS
- **AWS RDS MySQL** (db.t4g.small): Shared by Puzzleboss + MediaWiki
- **ALB** with Let's Encrypt SSL on instances
- **Manual deployment** via `deploy.sh` (GitHub tarball pull + systemd restart)

## Target Architecture

```
Route 53 → ALB (ACM cert) → Path-based routing
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                   ▼
    ECS: Puzzleboss      ECS: MediaWiki     (other paths)
    (Fargate, 1-2 tasks) (Fargate, 1 task)
    1 vCPU / 3 GB        0.5 vCPU / 1 GB
    Apache+PHP+Gunicorn   Apache+PHP
              │                 │
              ▼                 ▼
         AWS RDS MySQL (unchanged, db.t4g.small)

    ECS: Memcache          ECS: BigJimmy
    (Fargate, 1 task)      (Fargate, 1 task)
    0.25 vCPU / 512 MB     0.5 vCPU / 1 GB

    EC2: Observability (t4g.small)
    Prometheus + Loki (S3 backend) + Grafana + Alloy

    S3: MediaWiki images (replaces NFS)
    S3: Loki log storage
    ECR: Container image repositories
```

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Container platform | ECS Fargate (ARM/Graviton) | No instance management, 20% ARM savings, leverages existing Dockerfile |
| SSL | ALB + ACM | Free auto-renewing certs, eliminates Let's Encrypt on instances |
| Memcache | Fargate container (not ElastiCache) | Cheaper (~$7 vs ~$12/mo), keeps everything in ECS, simpler mental model |
| MediaWiki | Separate ECS service | Independent scaling, clean separation, S3 for images replaces NFS |
| Auth | Keep Apache mod_auth_openidc | Proven, minimal code changes, OIDC sessions in memcache |
| Observability | Dedicated EC2 (t4g.small) | Survives ECS failures, Prometheus/Loki need persistence |
| IaC | Terraform with S3 backend | Industry standard, team-friendly, state in S3 |
| MediaWiki images | S3 bucket (replaces NFS) | Eliminates NFS SPOF, makes MediaWiki stateless for Fargate |
| Other web content | Same Puzzleboss container | /account, /sktsurvey bundled in; keeps container count low |

## Cost Estimates (us-east-1, ARM/Graviton, On-Demand)

### Hunt Month (January — full capacity)

| Component | Monthly |
|-----------|---------|
| ECS Fargate (5 tasks: 2×PB + MW + MC + BJ) | ~$99 |
| RDS db.t4g.small (20 GB gp3) | ~$26 |
| ALB + ACM | ~$35 |
| EC2 t4g.small (observability) | ~$16 |
| ECR + S3 + Route 53 + Cloud Map | ~$7 |
| **Total** | **~$182** |

### Idle Month (Feb–Dec — scaled down)

| Component | Monthly |
|-----------|---------|
| ECS Fargate (4 tasks: 1×PB + MW + MC + BJ-small) | ~$60 |
| RDS db.t4g.small | ~$26 |
| ALB + ACM | ~$19 |
| EC2 t4g.small (observability) | ~$16 |
| ECR + S3 + Route 53 + Cloud Map | ~$3 |
| **Total** | **~$124** |

### Aggressive Shutdown (terraform destroy)

| Component | Monthly |
|-----------|---------|
| RDS storage only (stopped) | ~$2 |
| S3 + ECR + Route 53 | ~$2 |
| **Total** | **~$5** |

### Annual: ~$1,546 (always-on) or ~$250 (shutdown idle)

## Sizing Details

- **70 concurrent users** during hunt
- **250 puzzles**, 30,000-event activity log
- **Gunicorn**: 4 workers per Fargate task × 2 tasks = 8 total (matches current)
- **BigJimmy**: 3-4 threads, I/O-bound (Google Sheets polling)
- **RDS connections**: ~25 peak concurrent out of ~150 max — plenty of headroom
- **Memcache**: OIDC sessions (~70 × 2 KB) + puzzle cache (~500 KB) = well under 100 MB

## Terraform Structure

```
terraform/
├── main.tf              # Provider, S3 backend
├── variables.tf         # Input variables
├── outputs.tf           # ALB DNS, endpoints, etc.
├── versions.tf          # Required providers
├── bootstrap.sh         # One-time S3 state bucket setup
│
├── network.tf           # VPC, subnets, security groups
├── alb.tf               # ALB, listeners, target groups, ACM
├── ecs.tf               # ECS cluster, task defs, services
├── rds.tf               # RDS (import existing)
├── s3.tf                # MediaWiki images, Loki storage
├── ecr.tf               # Container image repositories
├── observability.tf     # EC2 for Prometheus/Loki/Grafana
├── dns.tf               # Route 53 records
├── iam.tf               # Roles and policies
│
├── terraform.tfvars.example
└── .terraform.lock.hcl
```

## Deployment Workflow

### App deploys (code changes)
```bash
docker build → docker push to ECR → aws ecs update-service --force-new-deployment
```

### Infrastructure changes
```bash
cd terraform && terraform plan && terraform apply
```

### Hunt scaling
```bash
# Edit terraform.tfvars: puzzleboss_desired_count = 2
terraform apply
```

## Migration Steps

1. Create S3 state bucket and DynamoDB lock table (bootstrap.sh)
2. Write Terraform for all components
3. `terraform import` existing RDS and ALB
4. Build and push container images to ECR
5. Stand up ECS services alongside existing EC2 (parallel run)
6. Switch ALB target groups from EC2 to ECS
7. Verify everything works
8. Decommission old EC2 instances and series-of-tubes
