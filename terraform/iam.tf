# -----------------------------------------------------------------------------
# ECS Task Execution Role — used by ECS agent to pull images, write logs
# This is the role ECS itself uses, not your application code.
# -----------------------------------------------------------------------------

resource "aws_iam_role" "ecs_execution" {
  name = "${var.project_name}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_base" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow ECS agent to fetch secrets from Secrets Manager at container launch.
# This is the EXECUTION role (not the task role) — ECS itself reads the secret
# values and injects them as env vars before your app code starts.
resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "${var.project_name}-execution-secrets"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
      ]
      Resource = [
        aws_secretsmanager_secret.oidc_client_id.arn,
        aws_secretsmanager_secret.oidc_client_secret.arn,
        aws_secretsmanager_secret.oidc_crypto_passphrase.arn,
        aws_secretsmanager_secret.puzzleboss_yaml.arn,
        aws_secretsmanager_secret.google_sa_json.arn,
        aws_secretsmanager_secret.mediawiki_localsettings.arn,
      ]
    }]
  })
}

# -----------------------------------------------------------------------------
# ECS Task Role — used by your application code running inside containers
# This is what pbrest.py, bigjimmybot.py, etc. can do with AWS services.
# -----------------------------------------------------------------------------

resource "aws_iam_role" "ecs_task" {
  name = "${var.project_name}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

# Allow tasks to write CloudWatch logs
resource "aws_iam_role_policy" "ecs_task_logs" {
  name = "${var.project_name}-task-logs"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
      ]
      Resource = "${aws_cloudwatch_log_group.ecs.arn}:*"
    }]
  })
}

# Allow tasks to access the MediaWiki S3 bucket (for image uploads/reads)
resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "${var.project_name}-task-s3"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation",
      ]
      Resource = [
        aws_s3_bucket.mediawiki_images.arn,
        "${aws_s3_bucket.mediawiki_images.arn}/*",
      ]
    }]
  })
}

# Allow ECS task to use service discovery (Cloud Map)
resource "aws_iam_role_policy" "ecs_task_servicediscovery" {
  name = "${var.project_name}-task-sd"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "servicediscovery:DiscoverInstances",
      ]
      Resource = "*"
    }]
  })
}

# -----------------------------------------------------------------------------
# CloudWatch Log Group — shared by all ECS tasks
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-ecs-logs"
  }
}
