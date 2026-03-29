#!/bin/bash
set -e

echo "=== MediaWiki Production Entrypoint ==="

# ──────────────────────────────────────────────────────────────
# 1. Generate OIDC secrets file from environment variables
# ──────────────────────────────────────────────────────────────

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
    echo "WARNING: No OIDC credentials found. Creating placeholder..."
    cat > "$OIDC_SECRETS_FILE" <<EOF
OIDCClientID placeholder
OIDCClientSecret placeholder
OIDCCryptoPassphrase placeholder
EOF
fi

# ──────────────────────────────────────────────────────────────
# 2. Inject LocalSettings.php if provided via environment
# ──────────────────────────────────────────────────────────────
# MEDIAWIKI_LOCAL_SETTINGS is injected as a plain-text env var from
# Secrets Manager. Use printf to write it safely.

if [ -n "$MEDIAWIKI_LOCAL_SETTINGS" ]; then
    echo "Writing LocalSettings.php from MEDIAWIKI_LOCAL_SETTINGS..."
    printf '%s' "$MEDIAWIKI_LOCAL_SETTINGS" > /var/www/html/LocalSettings.php
    chown www-data:www-data /var/www/html/LocalSettings.php
    echo "LocalSettings.php written."
elif [ -f /var/www/html/LocalSettings.php ]; then
    echo "Using existing LocalSettings.php."
else
    echo "WARNING: /var/www/html/LocalSettings.php not found!"
    echo "MediaWiki will show the installation wizard."
    echo "Set MEDIAWIKI_LOCAL_SETTINGS or mount LocalSettings.php."
fi

# ──────────────────────────────────────────────────────────────
# 3. Create health check file (exercises PHP + DB connection)
# ──────────────────────────────────────────────────────────────
cat > /var/www/html/health.php <<'HEALTHEOF'
<?php
// Minimal health check: proves PHP works, LocalSettings.php loads, DB connects
header('Content-Type: text/plain');
try {
    require_once '/var/www/html/LocalSettings.php';
    $conn = new mysqli($wgDBserver, $wgDBuser, $wgDBpassword, $wgDBname);
    if ($conn->connect_error) {
        http_response_code(503);
        echo "DB ERROR";
        exit;
    }
    $conn->close();
    echo "OK";
} catch (Exception $e) {
    http_response_code(503);
    echo "ERROR";
}
HEALTHEOF
chown www-data:www-data /var/www/html/health.php

# ──────────────────────────────────────────────────────────────
# 4. Fix permissions on images directory
# ──────────────────────────────────────────────────────────────
chown -R www-data:www-data /var/www/html/images 2>/dev/null || true

echo "=== Starting Apache ==="
exec "$@"
