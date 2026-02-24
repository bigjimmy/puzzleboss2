# -----------------------------------------------------------------------------
# General
# -----------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (e.g., prod, staging)"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "puzzleboss"
}

# -----------------------------------------------------------------------------
# Network (existing default VPC — not managed by Terraform)
# -----------------------------------------------------------------------------

variable "vpc_id" {
  description = "Existing VPC ID (default VPC)"
  type        = string
  default     = "vpc-b5d8ffcf"
}

variable "subnet_ids" {
  description = "Subnet IDs for ECS tasks and ALB (at least 2 in different AZs)"
  type        = list(string)
  default     = ["subnet-82a278cf", "subnet-a71106fb"] # us-east-1a, us-east-1b
}

# -----------------------------------------------------------------------------
# DNS / SSL
# -----------------------------------------------------------------------------

variable "domain_name" {
  description = "Primary domain name (e.g., importanthuntpoll.org)"
  type        = string
}

variable "route53_zone_id" {
  description = "Existing Route 53 hosted zone ID (leave empty to create new)"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# RDS (existing — will be imported)
# -----------------------------------------------------------------------------

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.small"
}

variable "rds_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 20
}

variable "rds_instance_identifier" {
  description = "Existing RDS instance identifier (for import)"
  type        = string
  default     = "wind-up-birds"
}

variable "rds_database_name" {
  description = "MySQL default database name (empty string if none)"
  type        = string
  default     = ""
}

variable "rds_username" {
  description = "RDS master username (the AWS-level admin user, not app users)"
  type        = string
  default     = "admin"
  sensitive   = true
}

variable "rds_password" {
  description = "MySQL master password"
  type        = string
  sensitive   = true
}

# -----------------------------------------------------------------------------
# ECS — Puzzleboss
# -----------------------------------------------------------------------------

variable "puzzleboss_cpu" {
  description = "CPU units for Puzzleboss task (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "puzzleboss_memory" {
  description = "Memory in MB for Puzzleboss task"
  type        = number
  default     = 3072
}

variable "puzzleboss_desired_count" {
  description = "Number of Puzzleboss tasks (1 for idle, 2 for hunt)"
  type        = number
  default     = 1
}

variable "puzzleboss_gunicorn_workers" {
  description = "Number of Gunicorn workers per task"
  type        = number
  default     = 4
}

# -----------------------------------------------------------------------------
# ECS — MediaWiki
# -----------------------------------------------------------------------------

variable "mediawiki_cpu" {
  description = "CPU units for MediaWiki task"
  type        = number
  default     = 512
}

variable "mediawiki_memory" {
  description = "Memory in MB for MediaWiki task"
  type        = number
  default     = 1024
}

variable "mediawiki_desired_count" {
  description = "Number of MediaWiki tasks"
  type        = number
  default     = 1
}

# -----------------------------------------------------------------------------
# ECS — BigJimmy
# -----------------------------------------------------------------------------

variable "bigjimmy_cpu" {
  description = "CPU units for BigJimmy task (512 for hunt, 256 for idle)"
  type        = number
  default     = 256
}

variable "bigjimmy_memory" {
  description = "Memory in MB for BigJimmy task (1024 for hunt, 512 for idle)"
  type        = number
  default     = 512
}

# -----------------------------------------------------------------------------
# ECS — Memcache
# -----------------------------------------------------------------------------

variable "memcache_cpu" {
  description = "CPU units for Memcache task"
  type        = number
  default     = 256
}

variable "memcache_memory" {
  description = "Memory in MB for Memcache task"
  type        = number
  default     = 512
}

# -----------------------------------------------------------------------------
# Observability EC2
# -----------------------------------------------------------------------------

variable "observability_instance_type" {
  description = "EC2 instance type for observability stack"
  type        = string
  default     = "t4g.small"
}

variable "observability_volume_size" {
  description = "EBS volume size in GB for observability instance"
  type        = number
  default     = 30
}

variable "ssh_key_name" {
  description = "EC2 key pair name for SSH access to observability instance"
  type        = string
  default     = ""
}

variable "ssh_allowed_cidrs" {
  description = "CIDR blocks allowed to SSH to observability instance"
  type        = list(string)
  default     = []
}

# -----------------------------------------------------------------------------
# OIDC Authentication (Google Workspace)
# -----------------------------------------------------------------------------
# Used by the ALB to gate access to Grafana (/metrics*).
# Puzzleboss and MediaWiki handle their own OIDC via Apache mod_auth_openidc.

variable "enable_dns_cutover" {
  description = "Set to true to create Route 53 records pointing domain to ALB (switches live traffic)"
  type        = bool
  default     = false
}

variable "oidc_client_id" {
  description = "Google OIDC client ID for ALB authentication"
  type        = string
  sensitive   = true
}

variable "oidc_client_secret" {
  description = "Google OIDC client secret for ALB authentication"
  type        = string
  sensitive   = true
}
