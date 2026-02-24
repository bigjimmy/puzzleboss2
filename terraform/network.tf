# -----------------------------------------------------------------------------
# Network — Reusing the existing AWS Default VPC
# -----------------------------------------------------------------------------
#
# Your infrastructure runs in the default VPC (vpc-b5d8ffcf, 172.31.0.0/16).
# All subnets are public. ECS Fargate tasks get public IPs and use security
# groups for access control.
#
# We reference existing resources by ID rather than creating new ones.
# This means these resources are NOT managed by Terraform — Terraform
# won't modify or destroy them.
# -----------------------------------------------------------------------------

data "aws_vpc" "main" {
  id = var.vpc_id
}

data "aws_subnets" "all" {
  filter {
    name   = "vpc-id"
    values = [var.vpc_id]
  }
}

# Pick specific subnets for ECS and ALB — at least 2 AZs required for ALB
data "aws_subnet" "selected" {
  for_each = toset(var.subnet_ids)
  id       = each.value
}

# -----------------------------------------------------------------------------
# Security Groups — NEW, managed by Terraform
# -----------------------------------------------------------------------------

# ALB — accepts HTTPS from the internet
resource "aws_security_group" "alb" {
  name_prefix = "${var.project_name}-alb-"
  description = "ALB - allow inbound HTTP/HTTPS"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP (redirect to HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-alb-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ECS tasks — accepts traffic from ALB only
resource "aws_security_group" "ecs_tasks" {
  name_prefix = "${var.project_name}-ecs-"
  description = "ECS tasks - allow inbound from ALB"
  vpc_id      = var.vpc_id

  ingress {
    description     = "HTTP from ALB"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Allow ECS tasks to talk to each other (memcache, service discovery)
  ingress {
    description = "Inter-task communication"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    self        = true
  }

  # Prometheus scraping from observability instance (Flask API on :5000)
  ingress {
    description = "Prometheus scrape Flask API from VPC"
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.main.cidr_block]
  }

  # Prometheus scraping from observability instance (metrics.php on :80)
  # Note: port 80 from ALB SG is already covered above; this adds VPC-wide
  # access for Prometheus (observability instance is in the same VPC).
  ingress {
    description = "Prometheus scrape metrics.php from VPC"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.main.cidr_block]
  }

  egress {
    description = "All outbound (DB, Google APIs, ECR, etc.)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-ecs-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Observability instance — SSH + Prometheus/Grafana access
resource "aws_security_group" "observability" {
  name_prefix = "${var.project_name}-o11y-"
  description = "Observability instance - Prometheus, Grafana, Loki"
  vpc_id      = var.vpc_id

  # SSH access (restricted)
  dynamic "ingress" {
    for_each = length(var.ssh_allowed_cidrs) > 0 ? [1] : []
    content {
      description = "SSH (non-standard port)"
      from_port   = 3748
      to_port     = 3748
      protocol    = "tcp"
      cidr_blocks = var.ssh_allowed_cidrs
    }
  }

  # Prometheus scrape port — from within VPC
  ingress {
    description = "Prometheus from VPC"
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.main.cidr_block]
  }

  # Grafana — from ALB (proxied)
  ingress {
    description     = "Grafana from ALB"
    from_port       = 3000
    to_port         = 3000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Apache (phpMyAdmin, scripts, mailman archives) — from ALB
  ingress {
    description     = "Apache from ALB"
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Loki push endpoint — from ECS tasks (Alloy sidecar)
  ingress {
    description     = "Loki from ECS tasks"
    from_port       = 3100
    to_port         = 3100
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  # Node exporter — from within VPC
  ingress {
    description = "Node exporter from VPC"
    from_port   = 9100
    to_port     = 9100
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.main.cidr_block]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-o11y-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# RDS — allow MySQL from ECS tasks and observability instance
# NOTE: Your existing RDS uses sg-040633c96acefbef4 ("mystery-hunt-backend").
# We create a new SG for the Terraform-managed world. During migration you'll
# add this SG to the RDS instance alongside the existing one.
resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-rds-"
  description = "RDS - allow MySQL from ECS and observability"
  vpc_id      = var.vpc_id

  ingress {
    description     = "MySQL from ECS tasks"
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  ingress {
    description     = "MySQL from observability instance"
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.observability.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-rds-sg"
  }

  lifecycle {
    create_before_destroy = true
  }
}
