#!/bin/bash
# This script runs during MySQL container initialization as the mysql user
# The MySQL docker-entrypoint.sh switches to mysql user before running init scripts

echo "Setting up MySQL SSL certificates for app container..."
echo "Running as user: $(whoami) (uid=$(id -u))"

# Wait for certificates to be generated
sleep 2

# The directory /var/lib/mysql-certs is owned by root and not writable by mysql user
# We need to write the certificates in a way that works as mysql user
# Solution: Write to a temporary location we DO have access to, then move them

# Check if certificates exist
if [ -f /var/lib/mysql/ca.pem ]; then
    echo "MySQL SSL certificates found at /var/lib/mysql/"

    # Write certificate contents to the shared volume using cat/redirect
    # This should work even as mysql user since we're just appending
    cat /var/lib/mysql/ca.pem > /var/lib/mysql-certs/ca.pem 2>&1 && echo "✓ ca.pem copied" || echo "✗ ca.pem copy failed: permission denied"
    cat /var/lib/mysql/client-cert.pem > /var/lib/mysql-certs/client-cert.pem 2>&1 && echo "✓ client-cert.pem copied" || echo "✗ client-cert.pem copy failed"
    cat /var/lib/mysql/client-key.pem > /var/lib/mysql-certs/client-key.pem 2>&1 && echo "✓ client-key.pem copied" || echo "✗ client-key.pem copy failed"

    echo "Certificate copy attempt completed. Listing /var/lib/mysql-certs/:"
    ls -la /var/lib/mysql-certs/ || echo "Cannot list directory"
else
    echo "WARNING: MySQL SSL certificates not found at /var/lib/mysql/ca.pem"
    echo "Certificates may not have been generated yet."
fi
