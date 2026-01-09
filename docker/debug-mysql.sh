#!/bin/bash
# MySQL Connection Debugging Script

echo "=== Step 1: Container Status ==="
docker-compose ps
echo ""

echo "=== Step 2: MySQL Container Logs (last 30 lines) ==="
docker-compose logs --tail=30 mysql
echo ""

echo "=== Step 3: MySQL Health Check ==="
docker inspect puzzleboss-mysql --format='{{.State.Health.Status}}' 2>&1
echo ""

echo "=== Step 4: Test MySQL from Host ==="
docker exec puzzleboss-mysql mysqladmin ping -u root -prootpassword 2>&1
echo ""

echo "=== Step 5: Test MySQL Connection from App Container ==="
if docker exec puzzleboss-app which mysql >/dev/null 2>&1; then
    docker exec puzzleboss-app mysql -h mysql -u puzzleboss -ppuzzleboss123 -e "SELECT 1 as test" 2>&1
else
    echo "mysql client not installed in app container (this is expected)"
    echo "Testing with Python instead..."
    docker exec puzzleboss-app python3 -c "import MySQLdb; conn = MySQLdb.connect('mysql', 'puzzleboss', 'puzzleboss123', 'puzzleboss'); print('Connection successful!')" 2>&1
fi
echo ""

echo "=== Step 6: Network Connectivity ==="
docker exec puzzleboss-app ping -c 3 mysql 2>&1
echo ""

echo "=== Step 7: MySQL Port Check ==="
docker exec puzzleboss-app nc -zv mysql 3306 2>&1 || echo "netcat not available, checking with telnet..."
echo ""

echo "=== Diagnosis ==="
echo "If you see:"
echo "  - 'Connection refused' → MySQL not started yet (wait longer)"
echo "  - 'Unknown host mysql' → Network issue (restart docker-compose)"
echo "  - 'Access denied' → Credentials wrong (check docker-compose.yml)"
echo "  - 'ping: 100% packet loss' → Network issue"
echo "  - '(healthy)' in health status → MySQL is ready, app should connect soon"
