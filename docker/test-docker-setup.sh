#!/bin/bash
# Quick validation script to check if Docker setup is ready to run

set -e

echo "=== Puzzleboss Docker Setup Validation ==="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
fi
echo "✓ Docker is installed"

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed"
    exit 1
fi
echo "✓ docker-compose is installed"

# Check if required files exist
REQUIRED_FILES=(
    "Dockerfile"
    "docker-compose.yml"
    "puzzleboss-docker.yaml"
    "docker/apache-site.conf"
    "docker/supervisord.conf"
    "docker/docker-entrypoint.sh"
    "scripts/puzzleboss.sql"
    "requirements.txt"
    "wsgi.py"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Missing file: $file"
        exit 1
    fi
done
echo "✓ All required files present"

# Check if entrypoint is executable
if [ ! -x "docker/docker-entrypoint.sh" ]; then
    echo "⚠️  docker-entrypoint.sh is not executable, fixing..."
    chmod +x docker/docker-entrypoint.sh
fi
echo "✓ Entrypoint script is executable"

# Check if port 80 is available
if lsof -Pi :80 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 80 is already in use - you may need to stop the other service"
    echo "   (This usually requires sudo/admin privileges)"
else
    echo "✓ Port 80 is available"
fi

# Check if port 5000 is available
if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 5000 is already in use - you may need to stop the other service"
else
    echo "✓ Port 5000 is available"
fi

# Check if port 3306 is available
if lsof -Pi :3306 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Port 3306 is already in use - MySQL might already be running locally"
    echo "   You can either:"
    echo "   - Stop your local MySQL: sudo service mysql stop"
    echo "   - Change the port in docker-compose.yml (e.g., '3307:3306')"
else
    echo "✓ Port 3306 is available"
fi

echo ""
echo "=== Validation Complete ==="
echo ""
echo "To start Puzzleboss with Docker:"
echo "  docker-compose up --build"
echo ""
echo "Then access:"
echo "  Web UI:  http://localhost?assumedid=testuser"
echo "  API:     http://localhost:5000/apidocs"
echo ""
