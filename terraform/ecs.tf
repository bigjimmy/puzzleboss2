# -----------------------------------------------------------------------------
# ECS Cluster
# -----------------------------------------------------------------------------

resource "aws_ecs_cluster" "main" {
  name = var.project_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.project_name}-cluster"
  }
}

# -----------------------------------------------------------------------------
# Service Discovery — private DNS namespace for inter-service communication
# Creates a .local namespace so services can find each other by name:
#   memcache.puzzleboss.local:11211
# -----------------------------------------------------------------------------

resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${var.project_name}.local"
  vpc  = var.vpc_id

  tags = {
    Name = "${var.project_name}-sd-namespace"
  }
}

# =============================================================================
# PUZZLEBOSS — Web tier (Apache + PHP + Gunicorn)
# =============================================================================

resource "aws_service_discovery_service" "puzzleboss" {
  name = "puzzleboss"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

resource "aws_ecs_task_definition" "puzzleboss" {
  family                   = "${var.project_name}-web"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.puzzleboss_cpu
  memory                   = var.puzzleboss_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  # ARM/Graviton for 20% cost savings
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    # Fluent Bit log router — routes app container logs to Loki
    {
      name      = "log_router"
      image     = "public.ecr.aws/aws-observability/aws-for-fluent-bit:latest"
      essential = true
      user      = "0"

      firelensConfiguration = {
        type = "fluentbit"
        options = {
          "enable-ecs-log-metadata" = "true"
        }
      }

      # Fluent Bit's own operational logs go to CloudWatch
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "firelens"
        }
      }

      portMappings    = []
      systemControls  = []
      volumesFrom     = []
      memoryReservation = 50
    },
    {
      name      = "puzzleboss"
      image     = "${aws_ecr_repository.puzzleboss.repository_url}:latest"
      essential = true

      portMappings = [
        { containerPort = 80, hostPort = 80, protocol = "tcp" },     # Apache
        { containerPort = 5000, hostPort = 5000, protocol = "tcp" }, # Gunicorn
      ]

      environment = [
        { name = "GUNICORN_WORKERS", value = tostring(var.puzzleboss_gunicorn_workers) },
        { name = "ENVIRONMENT", value = var.environment },
        { name = "PYTHONUNBUFFERED", value = "1" },
        { name = "prometheus_multiproc_dir", value = "/dev/shm/puzzleboss_prometheus" },
      ]

      # Secrets fetched from Secrets Manager by ECS agent at launch time.
      # The container sees these as normal env vars (OIDC_CLIENT_ID, etc.).
      secrets = [
        { name = "OIDC_CLIENT_ID", valueFrom = aws_secretsmanager_secret.oidc_client_id.arn },
        { name = "OIDC_CLIENT_SECRET", valueFrom = aws_secretsmanager_secret.oidc_client_secret.arn },
        { name = "OIDC_CRYPTO_PASSPHRASE", valueFrom = aws_secretsmanager_secret.oidc_crypto_passphrase.arn },
        { name = "PUZZLEBOSS_YAML_B64", valueFrom = aws_secretsmanager_secret.puzzleboss_yaml.arn },
        { name = "GOOGLE_SA_JSON_B64", valueFrom = aws_secretsmanager_secret.google_sa_json.arn },
      ]

      # Logs routed via Fluent Bit sidecar → Loki on observability instance
      logConfiguration = {
        logDriver = "awsfirelens"
        options = {
          "Name"       = "loki"
          "Host"       = aws_instance.observability.private_ip
          "Port"       = "3100"
          "labels"     = "job=ecs, service=puzzleboss"
          "label_keys"  = "$source"
          "remove_keys" = "container_id,ecs_task_arn,ecs_task_definition,ecs_cluster,container_name"
          "line_format"  = "json"
        }
      }

      systemControls = []
      volumesFrom    = []
    }
  ])

  tags = {
    Name = "${var.project_name}-web-task"
  }
}

resource "aws_ecs_service" "puzzleboss" {
  name            = "puzzleboss"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.puzzleboss.arn
  desired_count   = var.puzzleboss_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.puzzleboss.arn
    container_name   = "puzzleboss"
    container_port   = 80
  }

  service_registries {
    registry_arn = aws_service_discovery_service.puzzleboss.arn
  }

  # Allow ECS to manage task count during deployments
  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  # Use rolling deployment
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener.https]

  tags = {
    Name = "${var.project_name}-web-service"
  }

  lifecycle {
    # Don't revert desired_count if it was changed via autoscaling or CLI
    ignore_changes = [task_definition]
  }
}

# =============================================================================
# MEDIAWIKI
# =============================================================================

resource "aws_ecs_task_definition" "mediawiki" {
  family                   = "${var.project_name}-mediawiki"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.mediawiki_cpu
  memory                   = var.mediawiki_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "log_router"
      image     = "public.ecr.aws/aws-observability/aws-for-fluent-bit:latest"
      essential = true
      user      = "0"
      firelensConfiguration = {
        type = "fluentbit"
        options = { "enable-ecs-log-metadata" = "true" }
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "firelens"
        }
      }
      portMappings      = []
      systemControls    = []
      volumesFrom       = []
      memoryReservation = 50
    },
    {
      name      = "mediawiki"
      image     = "${aws_ecr_repository.mediawiki.repository_url}:latest"
      essential = true

      portMappings = [
        { containerPort = 80, hostPort = 80, protocol = "tcp" },
      ]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
      ]

      secrets = [
        { name = "OIDC_CLIENT_ID", valueFrom = aws_secretsmanager_secret.oidc_client_id.arn },
        { name = "OIDC_CLIENT_SECRET", valueFrom = aws_secretsmanager_secret.oidc_client_secret.arn },
        { name = "OIDC_CRYPTO_PASSPHRASE", valueFrom = aws_secretsmanager_secret.oidc_crypto_passphrase.arn },
        { name = "MEDIAWIKI_LOCAL_SETTINGS_B64", valueFrom = aws_secretsmanager_secret.mediawiki_localsettings.arn },
      ]

      logConfiguration = {
        logDriver = "awsfirelens"
        options = {
          "Name"       = "loki"
          "Host"       = aws_instance.observability.private_ip
          "Port"       = "3100"
          "labels"     = "job=ecs, service=mediawiki"
          "label_keys"  = "$source"
          "remove_keys" = "container_id,ecs_task_arn,ecs_task_definition,ecs_cluster,container_name"
          "line_format"  = "json"
        }
      }

      systemControls = []
      volumesFrom    = []
    }
  ])

  tags = {
    Name = "${var.project_name}-mediawiki-task"
  }
}

resource "aws_ecs_service" "mediawiki" {
  name            = "mediawiki"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.mediawiki.arn
  desired_count   = var.mediawiki_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.mediawiki.arn
    container_name   = "mediawiki"
    container_port   = 80
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  depends_on = [aws_lb_listener.https]

  tags = {
    Name = "${var.project_name}-mediawiki-service"
  }

  lifecycle {
    ignore_changes = [task_definition]
  }
}

# =============================================================================
# MEMCACHE — Service discovery provides stable DNS for OIDC sessions
# =============================================================================

resource "aws_service_discovery_service" "memcache" {
  name = "memcache"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

resource "aws_ecs_task_definition" "memcache" {
  family                   = "${var.project_name}-memcache"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.memcache_cpu
  memory                   = var.memcache_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "log_router"
      image     = "public.ecr.aws/aws-observability/aws-for-fluent-bit:latest"
      essential = true
      user      = "0"
      firelensConfiguration = {
        type = "fluentbit"
        options = { "enable-ecs-log-metadata" = "true" }
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "firelens"
        }
      }
      portMappings      = []
      systemControls    = []
      volumesFrom       = []
      memoryReservation = 50
    },
    {
      name      = "memcache"
      image     = "memcached:1.6-alpine"
      essential = true

      # Limit memory to container allocation minus overhead (minus Fluent Bit ~50MB)
      command = ["memcached", "-m", "334", "-u", "memcache"]

      portMappings = [
        { containerPort = 11211, hostPort = 11211, protocol = "tcp" },
      ]

      logConfiguration = {
        logDriver = "awsfirelens"
        options = {
          "Name"       = "loki"
          "Host"       = aws_instance.observability.private_ip
          "Port"       = "3100"
          "labels"     = "job=ecs, service=memcache"
          "label_keys"  = "$source"
          "remove_keys" = "container_id,ecs_task_arn,ecs_task_definition,ecs_cluster,container_name"
          "line_format"  = "json"
        }
      }

      systemControls = []
      volumesFrom    = []
    }
  ])

  tags = {
    Name = "${var.project_name}-memcache-task"
  }
}

resource "aws_ecs_service" "memcache" {
  name            = "memcache"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.memcache.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  service_registries {
    registry_arn = aws_service_discovery_service.memcache.arn
  }

  tags = {
    Name = "${var.project_name}-memcache-service"
  }

  lifecycle {
    ignore_changes = [task_definition]
  }
}

# =============================================================================
# BIGJIMMY — Sheet activity polling bot
# =============================================================================

resource "aws_ecs_task_definition" "bigjimmy" {
  family                   = "${var.project_name}-bigjimmy"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.bigjimmy_cpu
  memory                   = var.bigjimmy_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name      = "log_router"
      image     = "public.ecr.aws/aws-observability/aws-for-fluent-bit:latest"
      essential = true
      user      = "0"
      firelensConfiguration = {
        type = "fluentbit"
        options = { "enable-ecs-log-metadata" = "true" }
      }
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "firelens"
        }
      }
      portMappings      = []
      systemControls    = []
      volumesFrom       = []
      memoryReservation = 50
    },
    {
      name      = "bigjimmy"
      image     = "${aws_ecr_repository.puzzleboss.repository_url}:latest"
      essential = true

      # Override entrypoint to run bigjimmy instead of the web server
      command = ["python", "bigjimmybot.py"]

      environment = [
        { name = "ENVIRONMENT", value = var.environment },
        { name = "PYTHONUNBUFFERED", value = "1" },
      ]

      secrets = [
        { name = "PUZZLEBOSS_YAML_B64", valueFrom = aws_secretsmanager_secret.puzzleboss_yaml.arn },
        { name = "GOOGLE_SA_JSON_B64", valueFrom = aws_secretsmanager_secret.google_sa_json.arn },
      ]

      logConfiguration = {
        logDriver = "awsfirelens"
        options = {
          "Name"       = "loki"
          "Host"       = aws_instance.observability.private_ip
          "Port"       = "3100"
          "labels"     = "job=ecs, service=bigjimmy"
          "label_keys"  = "$source"
          "remove_keys" = "container_id,ecs_task_arn,ecs_task_definition,ecs_cluster,container_name"
          "line_format"  = "json"
        }
      }

      portMappings   = []
      systemControls = []
      volumesFrom    = []
    }
  ])

  tags = {
    Name = "${var.project_name}-bigjimmy-task"
  }
}

resource "aws_ecs_service" "bigjimmy" {
  name            = "bigjimmy"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.bigjimmy.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  # No load balancer — BigJimmy is a background daemon, not a web service.
  # No service discovery — nothing needs to connect to BigJimmy.

  tags = {
    Name = "${var.project_name}-bigjimmy-service"
  }

  lifecycle {
    ignore_changes = [task_definition]
  }
}
