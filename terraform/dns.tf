# -----------------------------------------------------------------------------
# Route 53 — DNS
# -----------------------------------------------------------------------------
#
# If you have an existing hosted zone, set var.route53_zone_id and use the
# import block in imports.tf. Otherwise, this creates a new one.
# -----------------------------------------------------------------------------

# Use existing zone or create new
resource "aws_route53_zone" "main" {
  count = var.route53_zone_id == "" ? 1 : 0
  name  = var.domain_name

  tags = {
    Name = "${var.project_name}-zone"
  }
}

locals {
  zone_id = var.route53_zone_id != "" ? var.route53_zone_id : aws_route53_zone.main[0].zone_id
}

# A record pointing domain to ALB
# Set var.enable_dns_cutover = true when ready to switch traffic from old EC2 to ALB
resource "aws_route53_record" "root" {
  count   = var.enable_dns_cutover ? 1 : 0
  zone_id = local.zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# Wildcard for any subdomains
resource "aws_route53_record" "wildcard" {
  count   = var.enable_dns_cutover ? 1 : 0
  zone_id = local.zone_id
  name    = "*.${var.domain_name}"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}

# mysql.importanthuntpoll.org — stable CNAME for ancillary services
# This lets configs use "mysql.importanthuntpoll.org" instead of the raw RDS
# endpoint, and survives RDS replacements (just update the CNAME target).
resource "aws_route53_record" "mysql" {
  zone_id = local.zone_id
  name    = "mysql.${var.domain_name}"
  type    = "CNAME"
  ttl     = 300
  records = ["${aws_db_instance.main.address}."]
}

# hunter.importanthuntpoll.org — public DNS for the observability instance
# Points to the Elastic IP so the address survives instance recreation.
# Used for direct SSH access and as a stable reference.
resource "aws_route53_record" "hunter" {
  zone_id = local.zone_id
  name    = "hunter.${var.domain_name}"
  type    = "A"
  ttl     = 300
  records = [aws_eip.observability.public_ip]
}
