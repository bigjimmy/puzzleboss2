# -----------------------------------------------------------------------------
# ACM Certificate — free SSL for the ALB
# -----------------------------------------------------------------------------

resource "aws_acm_certificate" "main" {
  domain_name               = var.domain_name
  subject_alternative_names = ["*.${var.domain_name}"]
  validation_method         = "DNS"

  tags = {
    Name = "${var.project_name}-cert"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# DNS validation records (auto-created in Route 53)
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id = local.zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]

  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

# -----------------------------------------------------------------------------
# Application Load Balancer
# -----------------------------------------------------------------------------

resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.subnet_ids

  enable_deletion_protection = true

  tags = {
    Name = "${var.project_name}-alb"
  }
}

# -----------------------------------------------------------------------------
# Listeners
# -----------------------------------------------------------------------------

# HTTP → HTTPS redirect
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# HTTPS listener — default sends to MediaWiki (wiki is the home page)
# Root URL / serves the wiki directly (no redirect).
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.main.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mediawiki.arn
  }
}

# -----------------------------------------------------------------------------
# Listener Rules — path-based routing
# -----------------------------------------------------------------------------

# /pb*, /apidocs*, /flasgger_static*, /apispec*, /oauth2callback → Puzzleboss
# These paths are served by the Puzzleboss container (Apache + Gunicorn).
# Each container handles its own OIDC auth via mod_auth_openidc → REMOTE_USER.
resource "aws_lb_listener_rule" "puzzleboss" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.puzzleboss.arn
  }

  condition {
    path_pattern {
      values = ["/pb*", "/apidocs*", "/flasgger_static*", "/apispec*", "/oauth2callback"]
    }
  }
}

# /account*, /register, /health → Puzzleboss (unauthenticated paths)
resource "aws_lb_listener_rule" "puzzleboss_public" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 11

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.puzzleboss.arn
  }

  condition {
    path_pattern {
      values = ["/account*", "/register*", "/health"]
    }
  }
}

# /metrics* → Observability (Grafana) — OIDC auth then forward
# ALB handles OIDC (Google Workspace), Grafana has anonymous Viewer access
# so authenticated team members don't need a separate Grafana login.
resource "aws_lb_listener_rule" "grafana" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 20

  action {
    type = "authenticate-oidc"
    order = 1

    authenticate_oidc {
      authorization_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
      client_id              = var.oidc_client_id
      client_secret          = var.oidc_client_secret
      issuer                 = "https://accounts.google.com"
      token_endpoint         = "https://oauth2.googleapis.com/token"
      user_info_endpoint     = "https://openidconnect.googleapis.com/v1/userinfo"

      # Restrict to team domain
      authentication_request_extra_params = {
        hd = "importanthuntpoll.org"
      }

      on_unauthenticated_request = "authenticate"
    }
  }

  action {
    type             = "forward"
    order            = 2
    target_group_arn = aws_lb_target_group.grafana.arn
  }

  condition {
    path_pattern {
      values = ["/metrics*"]
    }
  }
}

# /wiki* → MediaWiki
# The MediaWiki container handles its own OIDC auth via mod_auth_openidc → REMOTE_USER.
resource "aws_lb_listener_rule" "mediawiki" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 15

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mediawiki.arn
  }

  condition {
    path_pattern {
      values = ["/wiki*"]
    }
  }
}

# Everything else (including /) → Puzzleboss (default action on listener)

# -----------------------------------------------------------------------------
# Target Groups
# -----------------------------------------------------------------------------

resource "aws_lb_target_group" "puzzleboss" {
  name        = "${var.project_name}-pb"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip" # Fargate uses awsvpc — targets are ENI IPs

  health_check {
    enabled             = true
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 10
    interval            = 30
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = {
    Name = "${var.project_name}-pb-tg"
  }
}

resource "aws_lb_target_group" "mediawiki" {
  name        = "${var.project_name}-wiki"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 10
    interval            = 30
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = {
    Name = "${var.project_name}-wiki-tg"
  }
}

resource "aws_lb_target_group" "grafana" {
  name        = "${var.project_name}-grafana"
  port        = 3000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "instance"

  health_check {
    enabled             = true
    path                = "/metrics/api/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = {
    Name = "${var.project_name}-grafana-tg"
  }
}

# Register the observability EC2 instance in the Grafana target group
resource "aws_lb_target_group_attachment" "grafana" {
  target_group_arn = aws_lb_target_group.grafana.arn
  target_id        = aws_instance.observability.id
  port             = 3000
}

# -----------------------------------------------------------------------------
# Legacy Web Content — served from observability instance Apache (port 80)
# phpMyAdmin, team scripts, mailman archives
# -----------------------------------------------------------------------------

resource "aws_lb_target_group" "observability_web" {
  name        = "${var.project_name}-o11y-web"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "instance"

  health_check {
    enabled             = true
    path                = "/health"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = {
    Name = "${var.project_name}-o11y-web-tg"
  }
}

resource "aws_lb_target_group_attachment" "observability_web" {
  target_group_arn = aws_lb_target_group.observability_web.arn
  target_id        = aws_instance.observability.id
  port             = 80
}

# /phpmyadmin* → OIDC auth then forward to observability Apache
resource "aws_lb_listener_rule" "phpmyadmin" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 30

  action {
    type  = "authenticate-oidc"
    order = 1

    authenticate_oidc {
      authorization_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
      client_id              = var.oidc_client_id
      client_secret          = var.oidc_client_secret
      issuer                 = "https://accounts.google.com"
      token_endpoint         = "https://oauth2.googleapis.com/token"
      user_info_endpoint     = "https://openidconnect.googleapis.com/v1/userinfo"

      authentication_request_extra_params = {
        hd = var.domain_name
      }

      on_unauthenticated_request = "authenticate"
    }
  }

  action {
    type             = "forward"
    order            = 2
    target_group_arn = aws_lb_target_group.observability_web.arn
  }

  condition {
    path_pattern {
      values = ["/phpmyadmin*"]
    }
  }
}

# /scripts* → OIDC auth then forward to observability Apache
resource "aws_lb_listener_rule" "scripts" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 40

  action {
    type  = "authenticate-oidc"
    order = 1

    authenticate_oidc {
      authorization_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
      client_id              = var.oidc_client_id
      client_secret          = var.oidc_client_secret
      issuer                 = "https://accounts.google.com"
      token_endpoint         = "https://oauth2.googleapis.com/token"
      user_info_endpoint     = "https://openidconnect.googleapis.com/v1/userinfo"

      authentication_request_extra_params = {
        hd = var.domain_name
      }

      on_unauthenticated_request = "authenticate"
    }
  }

  action {
    type             = "forward"
    order            = 2
    target_group_arn = aws_lb_target_group.observability_web.arn
  }

  condition {
    path_pattern {
      values = ["/scripts*"]
    }
  }
}

# /mailmanarchives* → OIDC auth then forward to observability Apache
resource "aws_lb_listener_rule" "mailmanarchives" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 50

  action {
    type  = "authenticate-oidc"
    order = 1

    authenticate_oidc {
      authorization_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
      client_id              = var.oidc_client_id
      client_secret          = var.oidc_client_secret
      issuer                 = "https://accounts.google.com"
      token_endpoint         = "https://oauth2.googleapis.com/token"
      user_info_endpoint     = "https://openidconnect.googleapis.com/v1/userinfo"

      authentication_request_extra_params = {
        hd = var.domain_name
      }

      on_unauthenticated_request = "authenticate"
    }
  }

  action {
    type             = "forward"
    order            = 2
    target_group_arn = aws_lb_target_group.observability_web.arn
  }

  condition {
    path_pattern {
      values = ["/mailmanarchives*"]
    }
  }
}
