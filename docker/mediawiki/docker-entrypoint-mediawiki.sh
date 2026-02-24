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
# LocalSettings.php can be provided in three ways:
#   a) MEDIAWIKI_LOCAL_SETTINGS_B64 env var (base64-encoded)
#   b) Mounted via EFS or bind mount at /var/www/html/LocalSettings.php
#   c) Baked into a derived image

if [ -n "$MEDIAWIKI_LOCAL_SETTINGS_B64" ]; then
    echo "Decoding LocalSettings.php from MEDIAWIKI_LOCAL_SETTINGS_B64..."
    echo "$MEDIAWIKI_LOCAL_SETTINGS_B64" | base64 -d > /var/www/html/LocalSettings.php
    chown www-data:www-data /var/www/html/LocalSettings.php
    echo "LocalSettings.php written."
elif [ -f /var/www/html/LocalSettings.php ]; then
    echo "Using existing LocalSettings.php."
else
    echo "WARNING: /var/www/html/LocalSettings.php not found!"
    echo "MediaWiki will show the installation wizard."
    echo "Set MEDIAWIKI_LOCAL_SETTINGS_B64 or mount LocalSettings.php."
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
