provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "puzzleboss"
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}

# Data sources for account and region info
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Availability zones in the region
data "aws_availability_zones" "available" {
  state = "available"
}
