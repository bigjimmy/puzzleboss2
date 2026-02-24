#!/bin/bash
set -euo pipefail

# =============================================================================
# deploy-ecs.sh — Build, push, and deploy Puzzleboss to ECS Fargate
# =============================================================================
#
# Usage:
#   ./deploy-ecs.sh                    # Build and deploy all services
#   ./deploy-ecs.sh --service puzzleboss  # Deploy only puzzleboss web tier
#   ./deploy-ecs.sh --service bigjimmy    # Deploy only bigjimmy bot
#   ./deploy-ecs.sh --service mediawiki   # Deploy only mediawiki
#   ./deploy-ecs.sh --build-only          # Build and push images, don't restart
#   ./deploy-ecs.sh --tag v1.2.3          # Tag the image (default: git SHA)
#
# Prerequisites:
#   - AWS CLI configured (aws sts get-caller-identity should work)
#   - Docker with buildx support (for ARM64 cross-compilation)
#   - Terraform outputs available (run from repo root or terraform/ dir)
# =============================================================================

# ── Configuration (auto-detect from Terraform outputs) ──────
AWS_REGION="${AWS_REGION:-us-east-1}"
CLUSTER_NAME="${CLUSTER_NAME:-puzzleboss}"
ACCOUNT_ID=""
ECR_PB_REPO=""
ECR_MW_REPO=""

# Colors
if [ -t 1 ]; then
    GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RED='\033[0;31m'
    BOLD='\033[1m'; RESET='\033[0m'
else
    GREEN=''; YELLOW=''; RED=''; BOLD=''; RESET=''
fi

info()  { echo -e "${BOLD}[INFO]${RESET}  $*"; }
ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

# ── Parse arguments ─────────────────────────────────────────
SERVICE=""
BUILD_ONLY=false
IMAGE_TAG=""
SKIP_BUILD=false

while [ $# -gt 0 ]; do
    case "$1" in
        --service)
            shift; SERVICE="${1:-}"
            if [[ ! "$SERVICE" =~ ^(puzzleboss|bigjimmy|mediawiki)$ ]]; then
                error "Invalid service: $SERVICE (must be puzzleboss, bigjimmy, or mediawiki)"
                exit 1
            fi
            ;;
        --build-only) BUILD_ONLY=true ;;
        --skip-build) SKIP_BUILD=true ;;
        --tag) shift; IMAGE_TAG="${1:-}" ;;
        -h|--help)
            sed -n '/^# Usage:/,/^# ====/p' "$0" | sed 's/^# \?//'; exit 0
            ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

# ── Auto-detect AWS account and ECR repos ───────────────────
info "Detecting AWS configuration..."

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_PB_REPO="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/puzzleboss/puzzleboss"
ECR_MW_REPO="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/puzzleboss/mediawiki"

# Default tag: short git SHA + timestamp
if [ -z "$IMAGE_TAG" ]; then
    GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
    IMAGE_TAG="${GIT_SHA}"
fi

ok "Account: ${ACCOUNT_ID}, Region: ${AWS_REGION}"
ok "Image tag: ${IMAGE_TAG}"

# ── ECR Login ───────────────────────────────────────────────
info "Logging into ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | \
    docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ok "ECR login successful"

# ── Build & Push ────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

build_and_push_puzzleboss() {
    info "Building Puzzleboss image (ARM64)..."
    docker buildx build \
        --platform linux/arm64 \
        -f "${SCRIPT_DIR}/Dockerfile.prod" \
        -t "${ECR_PB_REPO}:${IMAGE_TAG}" \
        -t "${ECR_PB_REPO}:latest" \
        --push \
        "${SCRIPT_DIR}"
    ok "Puzzleboss image pushed: ${ECR_PB_REPO}:${IMAGE_TAG}"
}

build_and_push_mediawiki() {
    if [ -f "${SCRIPT_DIR}/Dockerfile.mediawiki" ]; then
        info "Building MediaWiki image (ARM64)..."
        docker buildx build \
            --platform linux/arm64 \
            -f "${SCRIPT_DIR}/Dockerfile.mediawiki" \
            -t "${ECR_MW_REPO}:${IMAGE_TAG}" \
            -t "${ECR_MW_REPO}:latest" \
            --push \
            "${SCRIPT_DIR}"
        ok "MediaWiki image pushed: ${ECR_MW_REPO}:${IMAGE_TAG}"
    else
        warn "Dockerfile.mediawiki not found — skipping MediaWiki build"
    fi
}

if [ "$SKIP_BUILD" = false ]; then
    case "$SERVICE" in
        puzzleboss|bigjimmy)
            # Both use the same image
            build_and_push_puzzleboss
            ;;
        mediawiki)
            build_and_push_mediawiki
            ;;
        "")
            # Build all
            build_and_push_puzzleboss
            build_and_push_mediawiki
            ;;
    esac
fi

if [ "$BUILD_ONLY" = true ]; then
    ok "Build complete (--build-only mode, skipping deploy)."
    exit 0
fi

# ── Force new deployment ────────────────────────────────────
force_deploy() {
    local svc_name=$1
    info "Forcing new deployment for service: ${svc_name}..."
    aws ecs update-service \
        --cluster "${CLUSTER_NAME}" \
        --service "${svc_name}" \
        --force-new-deployment \
        --region "${AWS_REGION}" \
        --output text --query 'service.serviceName' > /dev/null
    ok "Deployment triggered for ${svc_name}"
}

case "$SERVICE" in
    puzzleboss)
        force_deploy "puzzleboss"
        ;;
    bigjimmy)
        force_deploy "bigjimmy"
        ;;
    mediawiki)
        force_deploy "mediawiki"
        ;;
    "")
        # Deploy all services that use the puzzleboss image
        force_deploy "puzzleboss"
        force_deploy "bigjimmy"
        # Only deploy mediawiki if we built its image
        if [ -f "${SCRIPT_DIR}/Dockerfile.mediawiki" ]; then
            force_deploy "mediawiki"
        fi
        ;;
esac

# ── Wait for deployment ─────────────────────────────────────
echo ""
info "Deployments triggered. Monitor progress:"
info "  aws ecs describe-services --cluster ${CLUSTER_NAME} --services puzzleboss --query 'services[0].deployments'"
info "  aws ecs wait services-stable --cluster ${CLUSTER_NAME} --services puzzleboss"
echo ""
ok "Deploy complete! Image tag: ${IMAGE_TAG}"
