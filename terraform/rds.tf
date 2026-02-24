# -----------------------------------------------------------------------------
# RDS MySQL Instance — "wind-up-birds"
# -----------------------------------------------------------------------------
#
# This definition matches your existing db.t4g.small instance.
# Import it with:
#   terraform import aws_db_instance.main wind-up-birds
#
# After import, run `terraform plan` to see any drift.
# Common drift: parameter_group_name, backup_window, maintenance_window.
# Adjust this file to match reality.
# -----------------------------------------------------------------------------

resource "aws_db_instance" "main" {
  identifier = var.rds_instance_identifier

  engine         = "mysql"
  engine_version = "8.4"
  instance_class = var.rds_instance_class

  allocated_storage = var.rds_allocated_storage
  storage_type      = "gp2" # Currently gp2, consider upgrading to gp3 later
  storage_encrypted = false  # Currently unencrypted — can enable later (requires snapshot+restore)

  db_name  = var.rds_database_name != "" ? var.rds_database_name : null
  username = var.rds_username
  password = var.rds_password

  # Uses the default VPC's default subnet group
  db_subnet_group_name   = "default-vpc-b5d8ffcf"
  vpc_security_group_ids = [
    "sg-040633c96acefbef4",     # Existing "mystery-hunt-backend" SG
    aws_security_group.rds.id,   # New SG for ECS task access
  ]

  multi_az = false

  # Match current settings
  parameter_group_name    = "mysql84params"
  backup_retention_period = 3
  auto_minor_version_upgrade = false # Currently off — match reality
  copy_tags_to_snapshot      = true  # Currently on — match reality

  # CloudWatch log exports (currently enabled)
  enabled_cloudwatch_logs_exports = ["error", "general", "slowquery"]

  # CRITICAL: Don't accidentally delete the database
  deletion_protection = true
  skip_final_snapshot = false
  final_snapshot_identifier = "${var.project_name}-final-snapshot"

  performance_insights_enabled = false # Currently off

  tags = {
    Name = "${var.project_name}-db"
  }

  lifecycle {
    prevent_destroy = true

    # These may drift — ignore until intentionally changed
    ignore_changes = [
      engine_version,
      password,
      backup_window,
      maintenance_window,
    ]
  }
}
