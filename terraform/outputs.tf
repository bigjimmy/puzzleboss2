# -----------------------------------------------------------------------------
# Outputs — printed after `terraform apply`
# -----------------------------------------------------------------------------

output "alb_dns_name" {
  description = "ALB DNS name (use for CNAME or Route 53 alias)"
  value       = aws_lb.main.dns_name
}

output "domain_url" {
  description = "Primary URL"
  value       = "https://${var.domain_name}"
}

output "ecr_puzzleboss_url" {
  description = "ECR repository URL for Puzzleboss images"
  value       = aws_ecr_repository.puzzleboss.repository_url
}

output "ecr_mediawiki_url" {
  description = "ECR repository URL for MediaWiki images"
  value       = aws_ecr_repository.mediawiki.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name (for deploy commands)"
  value       = aws_ecs_cluster.main.name
}

output "rds_endpoint" {
  description = "RDS MySQL endpoint"
  value       = aws_db_instance.main.endpoint
}

output "memcache_dns" {
  description = "Memcache service discovery DNS name"
  value       = "memcache.${var.project_name}.local"
}

output "observability_private_ip" {
  description = "Observability instance private IP"
  value       = aws_instance.observability.private_ip
}

output "observability_public_ip" {
  description = "Observability Elastic IP (hunter.importanthuntpoll.org)"
  value       = aws_eip.observability.public_ip
}

output "mediawiki_images_bucket" {
  description = "S3 bucket for MediaWiki images"
  value       = aws_s3_bucket.mediawiki_images.id
}

output "loki_storage_bucket" {
  description = "S3 bucket for Loki log storage"
  value       = aws_s3_bucket.loki_storage.id
}

output "legacy_web_bucket" {
  description = "S3 bucket for legacy web content (scripts, mailman archives)"
  value       = aws_s3_bucket.legacy_web.id
}

output "deploy_commands" {
  description = "Quick reference: how to deploy app updates"
  value       = <<-EOT

    # ─── First-time setup: populate Secrets Manager ───
    # OIDC credentials (same Google OAuth client for ALB + container OIDC):
    aws secretsmanager put-secret-value --secret-id ${var.project_name}/oidc-client-id --secret-string "YOUR-GOOGLE-CLIENT-ID"
    aws secretsmanager put-secret-value --secret-id ${var.project_name}/oidc-client-secret --secret-string "YOUR-GOOGLE-CLIENT-SECRET"
    aws secretsmanager put-secret-value --secret-id ${var.project_name}/oidc-crypto-passphrase --secret-string "YOUR-OIDC-CRYPTO-PASSPHRASE"

    # Application config (base64-encode the files):
    aws secretsmanager put-secret-value --secret-id ${var.project_name}/puzzleboss-yaml --secret-string "$(base64 < puzzleboss.yaml)"
    aws secretsmanager put-secret-value --secret-id ${var.project_name}/google-sa-json --secret-string "$(base64 < service-account.json)"
    aws secretsmanager put-secret-value --secret-id ${var.project_name}/mediawiki-localsettings --secret-string "$(base64 < LocalSettings.php)"

    # ─── Build and push Puzzleboss image ───
    docker build -t ${aws_ecr_repository.puzzleboss.repository_url}:latest .
    docker push ${aws_ecr_repository.puzzleboss.repository_url}:latest
    aws ecs update-service --cluster ${aws_ecs_cluster.main.name} --service puzzleboss --force-new-deployment
    aws ecs update-service --cluster ${aws_ecs_cluster.main.name} --service bigjimmy --force-new-deployment

    # ─── Build and push MediaWiki image ───
    docker buildx build --platform linux/arm64 -f Dockerfile.mediawiki -t ${aws_ecr_repository.mediawiki.repository_url}:latest .
    docker push ${aws_ecr_repository.mediawiki.repository_url}:latest
    aws ecs update-service --cluster ${aws_ecs_cluster.main.name} --service mediawiki --force-new-deployment

    # ─── Data migration (run on old EC2 instance) ───
    # MediaWiki images to S3:
    aws s3 sync /var/www/mediawiki-current/images/ s3://${aws_s3_bucket.mediawiki_images.id}/ --exclude "*.php" --exclude "README" --exclude "lockdir/*"

    # Legacy web content to S3:
    aws s3 sync /var/www/scripts s3://${aws_s3_bucket.legacy_web.id}/scripts/
    aws s3 sync /var/www/mailmanarchives s3://${aws_s3_bucket.legacy_web.id}/mailmanarchives/

    # ─── Scale for hunt ───
    # Edit terraform.tfvars: puzzleboss_desired_count = 2
    # terraform apply

  EOT
}
