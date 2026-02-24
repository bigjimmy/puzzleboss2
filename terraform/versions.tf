terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "puzzleboss-terraform-state"
    key            = "puzzleboss/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "puzzleboss-terraform-locks"
    encrypt        = true
  }
}
