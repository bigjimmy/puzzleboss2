#!/bin/bash
set -e

echo "=== Puzzleboss Docker Entrypoint ==="

# Wait for MySQL to be fully ready
echo "Waiting for MySQL to be ready..."
until mysql -h mysql -u puzzleboss -ppuzzleboss123 --skip-ssl puzzleboss -e "SELECT 1" >/dev/null 2>&1; do
    echo "MySQL is unavailable - sleeping"
    sleep 2
done
echo "MySQL is ready!"

# Check if SSL is configured in puzzleboss.yaml and handle certificate setup
if grep -q "CA: /var/lib/mysql-certs/ca.pem" /app/puzzleboss.yaml 2>/dev/null; then
    if [ ! -f /var/lib/mysql-certs/ca.pem ]; then
        echo "SSL certificates not found in /var/lib/mysql-certs/"
        echo "Copying certificates from MySQL data directory (via MySQL query)..."

        # Use MySQL to read and output the certificate files
        # This works because both containers share the mysql_certs volume
        mysql -h mysql -u root -prootpassword --skip-ssl mysql -e "
            SELECT 'Copying SSL certificates...' AS status;
        " 2>/dev/null || echo "Note: Using puzzleboss user instead of root"

        # Try to read the certificate using shell access over mysql protocol is tricky
        # Instead, let's use a simpler approach: since both containers can access the volume,
        # we just need MySQL to write to it. But MySQL init scripts already tried that.
        #
        # The real issue is the init script runs as mysql user. Let's check if certs exist
        # in the MySQL container and warn the user.

        echo "WARNING: SSL certificates not available yet."
        echo "This can happen if:"
        echo "  1. MySQL container just started and hasn't run init scripts"
        echo "  2. The mysql-certs volume has permission issues"
        echo ""
        echo "The app will retry connecting. If this persists:"
        echo "  Run: docker-compose down -v && docker-compose up --build"
        echo ""
        echo "Or disable SSL temporarily by editing puzzleboss.yaml"
    else
        echo "SSL certificates found - MySQL SSL connections enabled."
    fi
else
    echo "SSL not configured in puzzleboss.yaml - using unencrypted connections."
fi

# Create log directories
mkdir -p /var/log/gunicorn /var/log/bigjimmybot

# Check if config table is populated (indicator that DB is initialized)
CONFIG_COUNT=$(mysql -h mysql -u puzzleboss -ppuzzleboss123 --skip-ssl puzzleboss -N -e "SELECT COUNT(*) FROM config" 2>/dev/null || echo "0")

if [ "$CONFIG_COUNT" -eq "0" ]; then
    echo "Database appears empty or config table not populated. Re-importing schema..."
    mysql -h mysql -u puzzleboss -ppuzzleboss123 --skip-ssl puzzleboss < /app/scripts/puzzleboss.sql
    echo "Schema imported successfully!"
else
    echo "Database already initialized (found $CONFIG_COUNT config entries)"
fi

# Create a test user in the solver table if it doesn't exist
echo "Creating test user if needed..."
mysql -h mysql -u puzzleboss -ppuzzleboss123 --skip-ssl puzzleboss <<-EOSQL
    INSERT IGNORE INTO solver (name, fullname)
    VALUES ('testuser', 'Test User');
EOSQL
echo "Test user ready!"

# Set test user as puzztech admin if privs table is empty
PRIVS_COUNT=$(mysql -h mysql -u puzzleboss -ppuzzleboss123 --skip-ssl puzzleboss -N -e "SELECT COUNT(*) FROM privs" 2>/dev/null || echo "0")
if [ "$PRIVS_COUNT" -eq "0" ]; then
    echo "Setting up admin privileges for test user..."
    TESTUSER_ID=$(mysql -h mysql -u puzzleboss -ppuzzleboss123 --skip-ssl puzzleboss -N -e "SELECT id FROM solver WHERE name='testuser'")
    mysql -h mysql -u puzzleboss -ppuzzleboss123 --skip-ssl puzzleboss <<-EOSQL
        INSERT INTO privs (uid, puzztech, puzzleboss)
        VALUES ($TESTUSER_ID, 'YES', 'YES');
EOSQL
    echo "Admin privileges granted to testuser!"
fi

# Update config values for Docker environment (localhost URLs)
echo "Updating config values for Docker environment..."
mysql -h mysql -u puzzleboss -ppuzzleboss123 --skip-ssl puzzleboss <<-EOSQL
    UPDATE config SET val = 'http://localhost/account' WHERE \`key\` = 'ACCT_URI';
    UPDATE config SET val = 'http://localhost' WHERE \`key\` = 'BIN_URI';
    UPDATE config SET val = 'localhost' WHERE \`key\` = 'DOMAINNAME';
    UPDATE config SET val = 'localhost' WHERE \`key\` = 'MAILRELAY';
    UPDATE config SET val = 'noreply@localhost' WHERE \`key\` = 'REGEMAIL';
    UPDATE config SET val = 'Puzzleboss Docker Test Team' WHERE \`key\` = 'TEAMNAME';
EOSQL
echo "Config values updated for Docker!"

echo "=== Starting services ==="
exec "$@"
