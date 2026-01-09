# Puzzleboss Docker Setup

This directory contains Docker configuration for running Puzzleboss in a local development environment.

## Quick Start

```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

Access the application:
- **Web UI**: http://localhost
- **API/Swagger**: http://localhost:5000/apidocs
- **MySQL**: localhost:3306 (user: puzzleboss, pass: puzzleboss123)

## Default Test Account

The setup automatically creates a test user with admin privileges:
- **Username**: `testuser`
- **Full Name**: Test User
- **Privileges**: puzztech and puzzleboss admin

The PHP frontend is configured in test mode, so you can access it using:
http://localhost?assumedid=testuser

## Architecture

### Single App Container
- **Apache** (port 80) - Serves PHP frontend from `/app/www`
- **Gunicorn** (port 5000) - Python Flask API
- **BigJimmy Bot** - Disabled by default (requires Google API setup)

Apache proxies `/api/*`, `/apidocs`, and `/metrics` to the Python backend.

### MySQL Container
- Automatically initializes with schema from `scripts/puzzleboss.sql`
- Data persists in Docker volume `mysql_data`

## Configuration

**No configuration needed!** The Docker image includes `puzzleboss.yaml` with Docker-ready defaults.

The default config is pre-configured for Docker with:
- MySQL host set to `mysql` (Docker service name)
- Test credentials (username: puzzleboss, password: puzzleboss123)
- All optional integrations disabled (Google, Discord, LDAP)
- Test mode enabled for PHP authentication

**To customize configuration:**
1. Create your own `puzzleboss.yaml` in the project root
2. Uncomment the volume mount in `docker-compose.yml`:
   ```yaml
   - ./puzzleboss.yaml:/app/puzzleboss.yaml
   ```
3. Rebuild: `docker-compose up --build`

For production deployment, create `puzzleboss.yaml` from the sample and change:
- `MYSQL.HOST` from "mysql" to your MySQL server (e.g., `127.0.0.1`)
- `MYSQL.PASSWORD` to a secure password

## Development Workflow

Code changes are live-reloaded via volume mounts:
- `www/` - PHP frontend
- `*.py` - Python backend
- `scripts/` - Scripts and schema
- `swag/` - API documentation

To reload Python after code changes:
```bash
docker-compose restart app
```

## Stopping and Cleaning Up

```bash
# Stop services
docker-compose down

# Remove volumes (deletes database data)
docker-compose down -v

# Rebuild after changes
docker-compose up --build
```

## Enabling Optional Features

### BigJimmy Bot (Google Sheets Integration)
1. Get Google API credentials and place in project root
2. Update `puzzleboss-docker.yaml`:
   - Set config variable `SKIP_GOOGLE_API: false`
3. Edit `docker/supervisord.conf`:
   - Set `autostart=true` for `[program:bigjimmybot]`
4. Rebuild: `docker-compose up --build`

### Discord Integration
1. Set up puzzcord daemon separately
2. Update database config table with `SKIP_PUZZCORD=false` and connection details

### LDAP
1. Configure LDAP server connection in database config table
2. Disable test mode in `www/puzzlebosslib.php`

## Troubleshooting

### Database Connection Errors
```bash
# Check MySQL is running
docker-compose ps

# View MySQL logs
docker-compose logs mysql

# Manually connect to database
docker exec -it puzzleboss-mysql mysql -u puzzleboss -ppuzzleboss123 puzzleboss
```

### API Not Starting
```bash
# View Gunicorn logs
docker-compose logs app

# Check if port 5000 is available
docker exec -it puzzleboss-app netstat -tlnp | grep 5000
```

### Permission Errors
```bash
# Reset file permissions (if needed)
chmod +x docker/docker-entrypoint.sh
```

## Production Notes

This Docker setup is optimized for local development. For production:
- Remove volume mounts in `docker-compose.yml`
- Use proper secrets management (not plaintext passwords)
- Configure Apache REMOTE_USER authentication
- Enable HTTPS/TLS
- Set up proper logging and monitoring
- Use production WSGI server configuration
