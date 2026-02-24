# -----------------------------------------------------------------------------
# ECS Events → Loki pipeline
#
# EventBridge captures ECS state-change events and delivers them to an SQS
# queue.  A small Python daemon on the observability instance long-polls SQS
# and pushes events to the local Loki instance.
#
# This gives us OOM kills, task state transitions, deployment events, and
# circuit-breaker activations as searchable log entries in Grafana/Loki.
# -----------------------------------------------------------------------------

# ── SQS Queue ────────────────────────────────────────────────────────────

resource "aws_sqs_queue" "ecs_events" {
  name                       = "${var.project_name}-ecs-events"
  message_retention_seconds  = 86400 # 1 day — events are ephemeral
  receive_wait_time_seconds  = 20    # Enable long polling by default
  visibility_timeout_seconds = 60    # Retry after 60s if not deleted

  tags = {
    Name = "${var.project_name}-ecs-events"
  }
}

# Allow EventBridge to send messages to the queue
resource "aws_sqs_queue_policy" "ecs_events" {
  queue_url = aws_sqs_queue.ecs_events.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowEventBridge"
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.ecs_events.arn
      Condition = {
        ArnEquals = {
          "aws:SourceArn" = aws_cloudwatch_event_rule.ecs_state_changes.arn
        }
      }
    }]
  })
}

# ── EventBridge Rule ─────────────────────────────────────────────────────

resource "aws_cloudwatch_event_rule" "ecs_state_changes" {
  name        = "${var.project_name}-ecs-state-changes"
  description = "Capture ECS task/service/deployment state changes for the puzzleboss cluster"

  event_pattern = jsonencode({
    source      = ["aws.ecs"]
    detail-type = [
      "ECS Task State Change",
      "ECS Service Action",
      "ECS Deployment State Change",
    ]
    detail = {
      clusterArn = ["arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:cluster/${var.project_name}"]
    }
  })

  tags = {
    Name = "${var.project_name}-ecs-state-changes"
  }
}

resource "aws_cloudwatch_event_target" "ecs_events_to_sqs" {
  rule = aws_cloudwatch_event_rule.ecs_state_changes.name
  arn  = aws_sqs_queue.ecs_events.arn
}

# ── IAM — allow observability instance to read from SQS ──────────────────

resource "aws_iam_role_policy" "observability_sqs" {
  name = "${var.project_name}-o11y-ecs-events-sqs"
  role = aws_iam_role.observability.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes",
      ]
      Resource = aws_sqs_queue.ecs_events.arn
    }]
  })
}
