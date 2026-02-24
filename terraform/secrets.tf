# -----------------------------------------------------------------------------
# AWS Secrets Manager — secrets injected into ECS containers at launch time
# -----------------------------------------------------------------------------
# ECS natively integrates with Secrets Manager: secrets are fetched by the
# ECS agent (execution role) and injected as environment variables.
# Application code never sees ARNs — just reads env vars like normal.
#
# After `terraform apply`, populate each secret's value via the AWS Console
# or CLI:
#
#   aws secretsmanager put-secret-value \
#     --secret-id puzzleboss/oidc-client-id \
#     --secret-string "YOUR-GOOGLE-CLIENT-ID"
#
# For JSON files (service-account.json, puzzleboss.yaml, LocalSettings.php),
# base64-encode first:
#
#   aws secretsmanager put-secret-value \
#     --secret-id puzzleboss/puzzleboss-yaml \
#     --secret-string "$(base64 < puzzleboss.yaml)"
#
#   aws secretsmanager put-secret-value \
#     --secret-id puzzleboss/google-sa-json \
#     --secret-string "$(base64 < service-account.json)"
#
#   aws secretsmanager put-secret-value \
#     --secret-id puzzleboss/mediawiki-localsettings \
#     --secret-string "$(base64 < LocalSettings.php)"
# -----------------------------------------------------------------------------

# OIDC credentials — shared by Puzzleboss + MediaWiki containers
# (Also used by the ALB directly via var.oidc_client_id/oidc_client_secret)
resource "aws_secretsmanager_secret" "oidc_client_id" {
  name        = "${var.project_name}/oidc-client-id"
  description = "Google OIDC client ID for mod_auth_openidc"

  tags = {
    Name = "${var.project_name}-oidc-client-id"
  }
}

resource "aws_secretsmanager_secret" "oidc_client_secret" {
  name        = "${var.project_name}/oidc-client-secret"
  description = "Google OIDC client secret for mod_auth_openidc"

  tags = {
    Name = "${var.project_name}-oidc-client-secret"
  }
}

# OIDC crypto passphrase — shared by Puzzleboss + MediaWiki containers
# This encrypts OIDC session cookies. Both containers MUST use the same
# passphrase so users don't get forced to re-auth when the ALB routes
# them from /wiki* to /pb* (different containers, same session cookie).
resource "aws_secretsmanager_secret" "oidc_crypto_passphrase" {
  name        = "${var.project_name}/oidc-crypto-passphrase"
  description = "Shared OIDC session cookie encryption passphrase"

  tags = {
    Name = "${var.project_name}-oidc-crypto-passphrase"
  }
}

# puzzleboss.yaml — base64-encoded, decoded by entrypoint script
# Contains MySQL credentials, API URI, feature flags
resource "aws_secretsmanager_secret" "puzzleboss_yaml" {
  name        = "${var.project_name}/puzzleboss-yaml"
  description = "Base64-encoded puzzleboss.yaml (MySQL creds, API config)"

  tags = {
    Name = "${var.project_name}-puzzleboss-yaml"
  }
}

# Google service account JSON key — base64-encoded
# Used by pbgooglelib.py for Domain-Wide Delegation (Drive, Sheets, Admin)
resource "aws_secretsmanager_secret" "google_sa_json" {
  name        = "${var.project_name}/google-sa-json"
  description = "Base64-encoded Google service account JSON key for DWD"

  tags = {
    Name = "${var.project_name}-google-sa-json"
  }
}

# MediaWiki LocalSettings.php — base64-encoded, decoded by entrypoint script
# Contains DB creds, wiki config, S3 extension settings
resource "aws_secretsmanager_secret" "mediawiki_localsettings" {
  name        = "${var.project_name}/mediawiki-localsettings"
  description = "Base64-encoded MediaWiki LocalSettings.php"

  tags = {
    Name = "${var.project_name}-mediawiki-localsettings"
  }
}
