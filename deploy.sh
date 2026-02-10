#!/bin/bash
set -euo pipefail

#
# deploy.sh — Download latest code from GitHub and deploy it.
#
# Usage: ./deploy.sh [OPTIONS]
#
# Options:
#   --restart-gunicorn   Restart the gunicorn service (puzzleboss2)
#   --restart-apache     Restart Apache (apache2)
#   --restart-bigjimmy   Restart the BigJimmy bot (bigjimmybot)
#   --restart-all        Restart all three services
#   --branch BRANCH      Deploy from BRANCH instead of master
#   -y, --yes            Skip confirmation prompt
#   -h, --help           Show this help message
#

REPO_BASE="https://github.com/bigjimmy/puzzleboss2/tarball"
BRANCH="master"
TMPDIR=""

# Colors (disabled if not a terminal)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    RED='\033[0;31m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    GREEN='' YELLOW='' RED='' BOLD='' RESET=''
fi

info()  { echo -e "${BOLD}[INFO]${RESET}  $*"; }
ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

cleanup() {
    if [ -n "$TMPDIR" ] && [ -d "$TMPDIR" ]; then
        rm -rf "$TMPDIR"
    fi
}
trap cleanup EXIT

usage() {
    sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# \?//'
    exit 0
}

# ── Parse arguments ──────────────────────────────────────────────

restart_gunicorn=false
restart_apache=false
restart_bigjimmy=false
skip_confirm=false

while [ $# -gt 0 ]; do
    case "$1" in
        --restart-gunicorn) restart_gunicorn=true ;;
        --restart-apache)   restart_apache=true ;;
        --restart-bigjimmy) restart_bigjimmy=true ;;
        --restart-all)
            restart_gunicorn=true
            restart_apache=true
            restart_bigjimmy=true
            ;;
        --branch)
            shift
            if [ $# -eq 0 ]; then
                error "--branch requires a value"
                exit 1
            fi
            BRANCH="$1"
            ;;
        -y|--yes) skip_confirm=true ;;
        -h|--help) usage ;;
        *)
            error "Unknown option: $1"
            echo "Run '$0 --help' for usage."
            exit 1
            ;;
    esac
    shift
done

# ── Summary ──────────────────────────────────────────────────────

echo ""
info "Deploy plan:"
info "  - Download latest code from GitHub ($BRANCH)"
info "  - Extract and copy into $(pwd)"
$restart_gunicorn && info "  - Restart gunicorn (puzzleboss2)"
$restart_apache   && info "  - Restart Apache (apache2)"
$restart_bigjimmy && info "  - Restart BigJimmy (bigjimmybot)"
echo ""

# ── Confirm ──────────────────────────────────────────────────────

if [ "$skip_confirm" = false ]; then
    read -rp "Proceed? [y/N] " answer
    case "$answer" in
        y|Y) ;;
        *)
            info "Aborted."
            exit 0
            ;;
    esac
fi

# ── Download ─────────────────────────────────────────────────────

TMPDIR=$(mktemp -d)
tarball="$TMPDIR/puzzleboss2.tar.gz"

REPO_URL="$REPO_BASE/$BRANCH"
info "Downloading latest code from GitHub ($BRANCH)..."
if ! curl -fSL "$REPO_URL" -o "$tarball"; then
    error "Failed to download tarball from $REPO_URL"
    exit 1
fi
ok "Downloaded tarball"

# ── Extract ──────────────────────────────────────────────────────

info "Extracting..."
tar -xzf "$tarball" -C "$TMPDIR"

# GitHub tarballs extract to a directory like bigjimmy-puzzleboss2-<sha>
extracted=$(find "$TMPDIR" -mindepth 1 -maxdepth 1 -type d | head -1)
if [ -z "$extracted" ]; then
    error "No directory found after extraction"
    exit 1
fi
ok "Extracted to $(basename "$extracted")"

# ── Deploy ───────────────────────────────────────────────────────

info "Copying files into $(pwd)..."
cp -a "$extracted"/. .
ok "Files deployed"

# ── Permissions ──────────────────────────────────────────────────

info "Setting script permissions..."
chmod +x deploy.sh
find scripts -name '*.py' -exec chmod +x {} + 2>/dev/null || true
ok "Permissions set"

# ── Restart services ─────────────────────────────────────────────

if $restart_gunicorn; then
    info "Restarting gunicorn (puzzleboss2)..."
    sudo systemctl restart puzzleboss2
    ok "Gunicorn restarted"
fi

if $restart_apache; then
    info "Restarting Apache (apache2)..."
    sudo systemctl restart apache2
    ok "Apache restarted"
fi

if $restart_bigjimmy; then
    info "Restarting BigJimmy (bigjimmybot)..."
    sudo systemctl restart bigjimmybot
    ok "BigJimmy restarted"
fi

# ── Done ─────────────────────────────────────────────────────────

echo ""
ok "Deploy complete!"
