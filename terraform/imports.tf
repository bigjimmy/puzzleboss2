# -----------------------------------------------------------------------------
# IMPORT BLOCKS — Existing AWS Resources
# -----------------------------------------------------------------------------
#
# These blocks tell Terraform to adopt existing resources instead of creating
# new ones. Uncomment the ones you want to import, then:
#
#   terraform plan    # verify it shows "will be imported" not "will be created"
#   terraform apply   # perform the import
#
# After a successful import, comment the blocks back out — they're one-time use.
#
# NOTE: The VPC, subnets, IGW, and route tables are NOT imported. They're
# referenced as data sources (data.aws_vpc.main, var.subnet_ids) so Terraform
# reads but doesn't manage them. This means `terraform destroy` won't touch
# your VPC or networking.
# -----------------------------------------------------------------------------

# --- RDS ---
# IMPORTANT: Import this before first `terraform apply` to avoid creating a
# duplicate database!
#
import {
  to = aws_db_instance.main
  id = "wind-up-birds"
}

# --- Route 53 Hosted Zone ---
# Your existing zone: Z06231973NK0NP1OVRDZT for importanthuntpoll.org
# Only needed if you set route53_zone_id = "" and let Terraform create the zone.
# Since we're using the existing zone ID directly, no import needed.

# --- S3 Bucket — Loki (already exists as "hunt-loki") ---
#
import {
  to = aws_s3_bucket.loki_storage
  id = "hunt-loki"
}
