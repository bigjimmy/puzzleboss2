#!/bin/bash
set -e

echo "=== Puzzleboss Production Entrypoint ==="

# ──────────────────────────────────────────────────────────────
# 1. Generate OIDC secrets file from environment variables
# ──────────────────────────────────────────────────────────────
# In production, OIDC client credentials are passed via ECS task
# environment variables or SSM Parameter Store. This generates
# the Apache include file that mod_auth_openidc needs.

OIDC_SECRETS_FILE="/etc/apache2/oidc-secrets.conf"

if [ -n "$OIDC_CLIENT_ID" ] && [ -n "$OIDC_CLIENT_SECRET" ]; then
    echo "Generating OIDC secrets from environment variables..."
    cat > "$OIDC_SECRETS_FILE" <<EOF
OIDCClientID ${OIDC_CLIENT_ID}
OIDCClientSecret ${OIDC_CLIENT_SECRET}
OIDCCryptoPassphrase ${OIDC_CRYPTO_PASSPHRASE:-$(openssl rand -hex 32)}
EOF
    chmod 600 "$OIDC_SECRETS_FILE"
    echo "OIDC secrets configured."
elif [ -f "$OIDC_SECRETS_FILE" ]; then
    echo "Using existing OIDC secrets file."
else
    echo "WARNING: No OIDC credentials found."
    echo "Set OIDC_CLIENT_ID, OIDC_CLIENT_SECRET environment variables."
    echo "Creating placeholder (auth will not work)..."
    cat > "$OIDC_SECRETS_FILE" <<EOF
# Placeholder — OIDC not configured
OIDCClientID placeholder
OIDCClientSecret placeholder
OIDCCryptoPassphrase placeholder
EOF
fi

# ──────────────────────────────────────────────────────────────
# 2. Write puzzleboss.yaml if provided via environment
# ──────────────────────────────────────────────────────────────
# PUZZLEBOSS_YAML is injected as a plain-text env var from Secrets Manager.
# Use printf to write it safely (preserves newlines, no trailing-newline risk).

if [ -n "$PUZZLEBOSS_YAML" ]; then
    echo "Writing puzzleboss.yaml from PUZZLEBOSS_YAML..."
    printf '%s' "$PUZZLEBOSS_YAML" > /app/puzzleboss.yaml
    echo "puzzleboss.yaml written."
elif [ ! -f /app/puzzleboss.yaml ]; then
    echo "ERROR: /app/puzzleboss.yaml not found and PUZZLEBOSS_YAML not set!"
    echo "The application will fail to start without database configuration."
    exit 1
fi

# ──────────────────────────────────────────────────────────────
# 3. Google service account credentials
# ──────────────────────────────────────────────────────────────
# Credentials are now stored in the puzzleboss config table as
# SERVICE_ACCOUNT_JSON and read at runtime by pbgooglelib.py.
# No file/env var needed here.

# ──────────────────────────────────────────────────────────────
# 4. Create ALB health check file
# ──────────────────────────────────────────────────────────────
mkdir -p /var/www/html
echo "OK" > /var/www/html/health.html

# ──────────────────────────────────────────────────────────────
# 5. Override Gunicorn workers if set via environment
# ──────────────────────────────────────────────────────────────
if [ -n "$GUNICORN_WORKERS" ]; then
    echo "Gunicorn workers: $GUNICORN_WORKERS (from environment)"
fi

# ──────────────────────────────────────────────────────────────
# 6. Create necessary directories
# ──────────────────────────────────────────────────────────────
mkdir -p /dev/shm/puzzleboss_prometheus
chmod 777 /dev/shm/puzzleboss_prometheus

echo "=== Starting services ==="
exec "$@"
