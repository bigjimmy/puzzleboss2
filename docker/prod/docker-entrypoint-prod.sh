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
# If PUZZLEBOSS_YAML_B64 is set, decode it into puzzleboss.yaml.
# This allows injecting the config via ECS task definition secrets.
# Alternatively, puzzleboss.yaml can be baked into the image or
# mounted via EFS.

if [ -n "$PUZZLEBOSS_YAML_B64" ]; then
    echo "Decoding puzzleboss.yaml from PUZZLEBOSS_YAML_B64..."
    echo "$PUZZLEBOSS_YAML_B64" | base64 -d > /app/puzzleboss.yaml
    echo "puzzleboss.yaml written."
elif [ ! -f /app/puzzleboss.yaml ]; then
    echo "ERROR: /app/puzzleboss.yaml not found and PUZZLEBOSS_YAML_B64 not set!"
    echo "The application will fail to start without database configuration."
    exit 1
fi

# ──────────────────────────────────────────────────────────────
# 3. Write Google service account JSON if provided via environment
# ──────────────────────────────────────────────────────────────
# pbgooglelib.py loads credentials via from_service_account_file(),
# which needs a real file on disk. Decode the base64 env var into
# the default location that _get_service_account_file() expects.

if [ -n "$GOOGLE_SA_JSON_B64" ]; then
    echo "Decoding service-account.json from GOOGLE_SA_JSON_B64..."
    echo "$GOOGLE_SA_JSON_B64" | base64 -d > /app/service-account.json
    chmod 600 /app/service-account.json
    echo "service-account.json written."
elif [ -f /app/service-account.json ]; then
    echo "Using existing service-account.json."
else
    echo "WARNING: No Google service account found."
    echo "Google Sheets integration will not work."
    echo "Set GOOGLE_SA_JSON_B64 or mount service-account.json."
fi

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
