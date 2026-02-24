# -----------------------------------------------------------------------------
# S3 Bucket — MediaWiki images (replaces NFS mount from series-of-tubes)
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "mediawiki_images" {
  bucket = "${var.project_name}-mediawiki-images"

  tags = {
    Name = "${var.project_name}-mediawiki-images"
  }
}

resource "aws_s3_bucket_versioning" "mediawiki_images" {
  bucket = aws_s3_bucket.mediawiki_images.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "mediawiki_images" {
  bucket = aws_s3_bucket.mediawiki_images.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "mediawiki_images" {
  bucket = aws_s3_bucket.mediawiki_images.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# S3 Bucket — Loki log storage (backend for Loki on observability instance)
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "loki_storage" {
  bucket = "hunt-loki" # Existing bucket — import with: terraform import aws_s3_bucket.loki_storage hunt-loki

  tags = {
    Name = "${var.project_name}-loki-logs"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "loki_storage" {
  bucket = aws_s3_bucket.loki_storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "loki_storage" {
  bucket = aws_s3_bucket.loki_storage.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle rule: transition old logs to cheaper storage, expire after 90 days
resource "aws_s3_bucket_lifecycle_configuration" "loki_storage" {
  bucket = aws_s3_bucket.loki_storage.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    filter {} # Apply to all objects in the bucket

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    expiration {
      days = 90
    }
  }
}

# -----------------------------------------------------------------------------
# S3 Bucket — Legacy web content (scripts, mailman archives)
# -----------------------------------------------------------------------------
# Upload from the old EC2 instance with:
#   aws s3 sync /var/www/scripts s3://puzzleboss-legacy-web/scripts/
#   aws s3 sync /var/www/mailmanarchives s3://puzzleboss-legacy-web/mailmanarchives/

resource "aws_s3_bucket" "legacy_web" {
  bucket = "${var.project_name}-legacy-web"

  tags = {
    Name = "${var.project_name}-legacy-web"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "legacy_web" {
  bucket = aws_s3_bucket.legacy_web.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "legacy_web" {
  bucket = aws_s3_bucket.legacy_web.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# IAM role + policies for observability instance
# -----------------------------------------------------------------------------
#
# The observability instance needs access to:
#   1. S3 — Loki stores log chunks in the hunt-loki bucket
#   2. S3 — Legacy web content (scripts, mailman archives) downloaded on boot
#   3. CloudWatch — Grafana queries container logs and ECS metrics directly
#   4. ECS — Discovery script finds Fargate task IPs for Prometheus scraping
# -----------------------------------------------------------------------------

resource "aws_iam_role" "observability" {
  name = "${var.project_name}-observability"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

# Loki S3 backend — read/write log chunks
resource "aws_iam_role_policy" "observability_loki_s3" {
  name = "${var.project_name}-o11y-loki-s3"
  role = aws_iam_role.observability.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
      ]
      Resource = [
        aws_s3_bucket.loki_storage.arn,
        "${aws_s3_bucket.loki_storage.arn}/*",
      ]
    }]
  })
}

# Legacy web content S3 — read-only download on boot
resource "aws_iam_role_policy" "observability_legacy_s3" {
  name = "${var.project_name}-o11y-legacy-s3"
  role = aws_iam_role.observability.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:ListBucket",
      ]
      Resource = [
        aws_s3_bucket.legacy_web.arn,
        "${aws_s3_bucket.legacy_web.arn}/*",
      ]
    }]
  })
}

# CloudWatch — Grafana reads container logs and ECS metrics
resource "aws_iam_role_policy" "observability_cloudwatch" {
  name = "${var.project_name}-o11y-cloudwatch"
  role = aws_iam_role.observability.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogsRead"
        Effect = "Allow"
        Action = [
          "logs:GetLogEvents",
          "logs:GetLogRecord",
          "logs:GetQueryResults",
          "logs:StartQuery",
          "logs:StopQuery",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:FilterLogEvents",
          "logs:GetLogDelivery",
          "logs:ListLogDeliveries",
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchMetricsRead"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "cloudwatch:DescribeAlarms",
        ]
        Resource = "*"
      },
    ]
  })
}

# ECS — Prometheus native aws_sd_configs (role: ecs) discovers Fargate task IPs
resource "aws_iam_role_policy" "observability_ecs_discovery" {
  name = "${var.project_name}-o11y-ecs-discovery"
  role = aws_iam_role.observability.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "ECSDiscovery"
      Effect = "Allow"
      Action = [
        "ecs:ListClusters",
        "ecs:DescribeClusters",
        "ecs:ListTasks",
        "ecs:DescribeTasks",
        "ecs:ListServices",
        "ecs:DescribeServices",
        "ec2:DescribeNetworkInterfaces",
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_instance_profile" "observability" {
  name = "${var.project_name}-observability"
  role = aws_iam_role.observability.name
}
