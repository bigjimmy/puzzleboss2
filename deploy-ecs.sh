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
#   ./deploy-ecs.sh --wait                # Build, deploy, and wait for stable
#   ./deploy-ecs.sh --build-only          # Build and push images, don't restart
#   ./deploy-ecs.sh --tag v1.2.3          # Tag the image (default: git SHA)
#
# Prerequisites:
#   - AWS CLI configured (aws sts get-caller-identity should work)
#   - Docker with buildx support (for ARM64 cross-compilation)
#   - (Optional) Terraform outputs for reference — see puzzleboss2-infra repo
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
WAIT=false

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
        --wait) WAIT=true ;;
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

DEPLOYED_SERVICES=()

case "$SERVICE" in
    puzzleboss)
        force_deploy "puzzleboss"
        DEPLOYED_SERVICES+=("puzzleboss")
        ;;
    bigjimmy)
        force_deploy "bigjimmy"
        DEPLOYED_SERVICES+=("bigjimmy")
        ;;
    mediawiki)
        force_deploy "mediawiki"
        DEPLOYED_SERVICES+=("mediawiki")
        ;;
    "")
        # Deploy all services that use the puzzleboss image
        force_deploy "puzzleboss"
        DEPLOYED_SERVICES+=("puzzleboss")
        force_deploy "bigjimmy"
        DEPLOYED_SERVICES+=("bigjimmy")
        # Only deploy mediawiki if we built its image
        if [ -f "${SCRIPT_DIR}/Dockerfile.mediawiki" ]; then
            force_deploy "mediawiki"
            DEPLOYED_SERVICES+=("mediawiki")
        fi
        ;;
esac

# ── Wait for stable (optional) ───────────────────────────────
wait_for_stable() {
    local services=("$@")
    local max_polls=40
    local poll_interval=15
    local poll=0

    echo ""
    info "Waiting for services to stabilize (polling every ${poll_interval}s, timeout ${max_polls} polls)..."
    echo ""

    while [ $poll -lt $max_polls ]; do
        sleep $poll_interval
        poll=$((poll + 1))
        local elapsed=$((poll * poll_interval))

        local all_stable=true
        local any_failed=false
        local status_line=""

        for svc in "${services[@]}"; do
            # Get deployment count, running/desired, and primary rollout state
            local dep_count running desired rollout_state svc_status

            dep_count=$(aws ecs describe-services \
                --cluster "${CLUSTER_NAME}" --services "${svc}" \
                --region "${AWS_REGION}" --output text \
                --query 'services[0].deployments | length(@)' 2>/dev/null || echo "0")

            running=$(aws ecs describe-services \
                --cluster "${CLUSTER_NAME}" --services "${svc}" \
                --region "${AWS_REGION}" --output text \
                --query 'services[0].runningCount' 2>/dev/null || echo "?")

            desired=$(aws ecs describe-services \
                --cluster "${CLUSTER_NAME}" --services "${svc}" \
                --region "${AWS_REGION}" --output text \
                --query 'services[0].desiredCount' 2>/dev/null || echo "?")

            rollout_state=$(aws ecs describe-services \
                --cluster "${CLUSTER_NAME}" --services "${svc}" \
                --region "${AWS_REGION}" --output text \
                --query 'services[0].deployments[?status==`PRIMARY`].rolloutState | [0]' 2>/dev/null || echo "UNKNOWN")

            if [ "$rollout_state" = "FAILED" ]; then
                svc_status="${RED}FAILED${RESET}"
                any_failed=true
            elif [ "$dep_count" -gt 1 ] 2>/dev/null; then
                svc_status="${YELLOW}rolling${RESET} (${running}/${desired})"
                all_stable=false
            elif [ "$rollout_state" = "COMPLETED" ] && [ "$running" = "$desired" ]; then
                # Check container health for services with health checks (bigjimmy)
                if [ "$svc" = "bigjimmy" ]; then
                    local task_arn health_status
                    task_arn=$(aws ecs list-tasks \
                        --cluster "${CLUSTER_NAME}" --service-name "${svc}" \
                        --region "${AWS_REGION}" --output text \
                        --query 'taskArns[0]' 2>/dev/null || echo "")
                    if [ -n "$task_arn" ] && [ "$task_arn" != "None" ]; then
                        health_status=$(aws ecs describe-tasks \
                            --cluster "${CLUSTER_NAME}" --tasks "${task_arn}" \
                            --region "${AWS_REGION}" --output text \
                            --query 'tasks[0].healthStatus' 2>/dev/null || echo "UNKNOWN")
                    else
                        health_status="UNKNOWN"
                    fi

                    if [ "$health_status" = "HEALTHY" ]; then
                        svc_status="${GREEN}healthy${RESET} (${running}/${desired})"
                    elif [ "$health_status" = "UNHEALTHY" ]; then
                        svc_status="${RED}unhealthy${RESET} (${running}/${desired})"
                        all_stable=false
                    else
                        svc_status="${YELLOW}starting${RESET} (${running}/${desired}, health: ${health_status})"
                        all_stable=false
                    fi
                else
                    svc_status="${GREEN}stable${RESET} (${running}/${desired})"
                fi
            else
                svc_status="${YELLOW}deploying${RESET} (${running}/${desired})"
                all_stable=false
            fi

            if [ -n "$status_line" ]; then
                status_line="${status_line}  "
            fi
            status_line="${status_line}${BOLD}${svc}${RESET}: ${svc_status}"
        done

        # Print status line
        if [ -t 1 ]; then
            printf "\r\033[K[%3ds] %b" "$elapsed" "$status_line"
        else
            printf "[%3ds] %s\n" "$elapsed" "$status_line"
        fi

        if $any_failed; then
            echo ""
            error "Deployment failed! Check ECS console for details."
            return 1
        fi
        if $all_stable; then
            echo ""
            ok "All services stable and healthy!"
            return 0
        fi
    done

    echo ""
    error "Timeout after $((max_polls * poll_interval))s — services not yet stable"
    warn "Services may still be converging. Check manually:"
    warn "  aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${services[*]} --query 'services[].{name:serviceName,deployments:deployments}'"
    return 2
}

if [ "$WAIT" = true ]; then
    wait_for_stable "${DEPLOYED_SERVICES[@]}"
    exit_code=$?
    echo ""
    ok "Deploy finished. Image tag: ${IMAGE_TAG}"
    exit $exit_code
else
    echo ""
    info "Deployments triggered. Monitor progress:"
    info "  aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${DEPLOYED_SERVICES[*]} --query 'services[].{name:serviceName,deployments:deployments}'"
    info "  Or re-run with --wait to watch automatically."
    echo ""
    ok "Deploy complete! Image tag: ${IMAGE_TAG}"
fi
