# -----------------------------------------------------------------------------
# Observability Instance — Prometheus, Loki, Grafana
# -----------------------------------------------------------------------------
#
# This is the only EC2 instance in the architecture. It runs the monitoring
# stack that observes everything else. Keeping it on a dedicated instance
# ensures it survives ECS failures.
#
# Provisioned via user_data — not a snowflake. Can be destroyed and recreated.
# Persistent data (Prometheus TSDB) lives on the EBS volume; Loki uses S3.
# -----------------------------------------------------------------------------

# Latest Ubuntu 24.04 LTS ARM image
data "aws_ami" "ubuntu_arm" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-arm64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  filter {
    name   = "architecture"
    values = ["arm64"]
  }
}

resource "aws_instance" "observability" {
  ami                    = data.aws_ami.ubuntu_arm.id
  instance_type          = var.observability_instance_type
  key_name               = var.ssh_key_name != "" ? var.ssh_key_name : null
  subnet_id              = var.subnet_ids[0]
  vpc_security_group_ids = [aws_security_group.observability.id]
  iam_instance_profile   = aws_iam_instance_profile.observability.name

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.observability_volume_size
    encrypted             = true
    delete_on_termination = false # preserve monitoring data
  }

  user_data = base64encode(templatefile("${path.module}/templates/observability-init.sh", {
    loki_s3_bucket     = aws_s3_bucket.loki_storage.id
    aws_region         = var.aws_region
    project_name       = var.project_name
    ecs_cluster        = aws_ecs_cluster.main.name
    rds_endpoint       = aws_db_instance.main.endpoint
    legacy_web_bucket  = aws_s3_bucket.legacy_web.id
  }))

  tags = {
    Name = "${var.project_name}-observability"
  }

  lifecycle {
    # Don't replace instance when AMI updates — upgrade in place instead
    ignore_changes = [ami, user_data]
  }
}

# Elastic IP — stable public address that survives instance recreation
resource "aws_eip" "observability" {
  domain = "vpc"

  tags = {
    Name = "${var.project_name}-observability"
  }
}

resource "aws_eip_association" "observability" {
  instance_id   = aws_instance.observability.id
  allocation_id = aws_eip.observability.id
}
