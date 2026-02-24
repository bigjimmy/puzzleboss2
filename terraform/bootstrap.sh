#!/bin/bash
# bootstrap.sh — One-time setup for Terraform S3 state backend
#
# Run this ONCE before the first `terraform init`.
# Creates the S3 bucket and DynamoDB table that store Terraform state.
# These resources are intentionally NOT managed by Terraform (chicken-and-egg).
#
# Usage:
#   ./bootstrap.sh [--region us-east-1]

set -euo pipefail

REGION="${1:-us-east-1}"
BUCKET="puzzleboss-terraform-state"
TABLE="puzzleboss-terraform-locks"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Bootstrapping Terraform state backend in ${REGION}...${NC}"

# Create S3 bucket for state
echo -n "Creating S3 bucket ${BUCKET}... "
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
    echo -e "${YELLOW}already exists${NC}"
else
    # us-east-1 does not use LocationConstraint
    if [ "$REGION" = "us-east-1" ]; then
        aws s3api create-bucket --bucket "$BUCKET" --region "$REGION"
    else
        aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION"
    fi
    echo -e "${GREEN}created${NC}"
fi

# Enable versioning (state history = undo button)
echo -n "Enabling bucket versioning... "
aws s3api put-bucket-versioning --bucket "$BUCKET" \
    --versioning-configuration Status=Enabled
echo -e "${GREEN}done${NC}"

# Enable encryption
echo -n "Enabling bucket encryption... "
aws s3api put-bucket-encryption --bucket "$BUCKET" \
    --server-side-encryption-configuration \
    '{"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}'
echo -e "${GREEN}done${NC}"

# Block public access
echo -n "Blocking public access... "
aws s3api put-public-access-block --bucket "$BUCKET" \
    --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
echo -e "${GREEN}done${NC}"

# Create DynamoDB table for state locking
echo -n "Creating DynamoDB lock table ${TABLE}... "
if aws dynamodb describe-table --table-name "$TABLE" --region "$REGION" >/dev/null 2>&1; then
    echo -e "${YELLOW}already exists${NC}"
else
    aws dynamodb create-table \
        --table-name "$TABLE" \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region "$REGION"
    echo -e "${GREEN}created${NC}"

    echo -n "Waiting for table to be active... "
    aws dynamodb wait table-exists --table-name "$TABLE" --region "$REGION"
    echo -e "${GREEN}ready${NC}"
fi

echo ""
echo -e "${GREEN}Terraform state backend is ready!${NC}"
echo ""
echo "Next steps:"
echo "  cd terraform"
echo "  terraform init"
echo "  terraform plan"
