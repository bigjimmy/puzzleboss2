# Puzzleboss Docker Quick Start Guide

## Step 1: Build and Start

```bash
# From the puzzleboss2 root directory
docker-compose up --build
```

This will:
- Build the app container with Python, Apache, and PHP
- Start MySQL container
- Auto-initialize the database schema
- Create testuser with admin privileges
- Update config values for localhost
- Start all services

**First-time build takes 2-3 minutes.** You'll see lots of output. Wait for:
```
puzzleboss-app    | ==> /var/log/apache2/access.log <==
puzzleboss-app    |
puzzleboss-app    | ==> /var/log/gunicorn/access.log <==
```

## Step 2: Verify Services are Running

In another terminal:
```bash
# Check container status
docker-compose ps

# Should show:
# puzzleboss-mysql - Up (healthy)
# puzzleboss-app   - Up
```

## Step 3: Test the Web UI

Open your browser to:
```
http://localhost?assumedid=testuser
```

You should see the Puzzleboss main interface with:
- "Hello, testuser!" greeting
- Empty rounds/puzzles (fresh database)
- Navigation links to pbtools, status page, etc.

## Step 4: Test the API/Swagger

Open your browser to:
```
http://localhost:5000/apidocs
```

You should see the Swagger API documentation interface.

### Try a test API call:

1. Click on **GET /solvers** endpoint
2. Click "Try it out"
3. Click "Execute"
4. You should see a response with testuser:
```json
{
  "status": "ok",
  "solvers": [
    {
      "id": 1,
      "name": "testuser",
      "fullname": "Test User",
      ...
    }
  ]
}
```

## Step 5: Test Adding Data

### Add a Round:
1. Go to http://localhost?assumedid=testuser
2. Click the "pbtools" link
3. Find "Add Round" section
4. Enter:
   - Name: "Test Round"
   - URL: "https://example.com/round1"
5. Click "Add Round"

### Add a Puzzle:
1. From pbtools, find "Add Puzzle" section
2. Enter:
   - Name: "Test Puzzle"
   - Round: Select "Test Round"
   - URL: "https://example.com/puzzle1"
   - Status: "New"
3. Click "Add Puzzle"

### Verify:
Go back to http://localhost?assumedid=testuser
You should now see "Test Round" with "Test Puzzle" listed.

## Step 6: Check Database Directly (Optional)

```bash
# Connect to MySQL
docker exec -it puzzleboss-mysql mysql -u puzzleboss -ppuzzleboss123 puzzleboss

# Run queries
mysql> SELECT * FROM solver;
mysql> SELECT * FROM config WHERE `key` = 'TEAMNAME';
mysql> SELECT id, name, status FROM puzzle;
mysql> exit
```

## Step 7: View Logs

```bash
# All logs
docker-compose logs

# Just app logs
docker-compose logs app

# Follow logs in real-time
docker-compose logs -f app

# Just API (Gunicorn) logs
docker exec puzzleboss-app tail -f /var/log/gunicorn/access.log
docker exec puzzleboss-app tail -f /var/log/gunicorn/error.log
```

## Step 8: Test Code Changes (Hot Reload)

The setup supports live code reloading:

### Test PHP changes:
1. Edit `www/index.php` - change the "Hello" message
2. Refresh browser - should see changes immediately

### Test Python changes:
1. Edit `pbrest.py` - add a print statement
2. Restart the app container:
   ```bash
   docker-compose restart app
   ```
3. Check logs to see your change

## Stopping and Cleaning Up

```bash
# Stop services (keeps data)
docker-compose down

# Stop and remove all data (fresh start)
docker-compose down -v

# Restart services
docker-compose up
```

## Troubleshooting

### Port 80 already in use?
If you get "port is already allocated":
```bash
# Check what's using port 80
sudo lsof -i :80

# Stop the service (macOS Apache example)
sudo apachectl stop

# Or edit docker-compose.yml to use different port:
ports:
  - "8080:80"  # Then access http://localhost:8080
```

### Database connection errors?
```bash
# Check MySQL is healthy
docker-compose ps

# Restart everything
docker-compose restart
```

### Changes not appearing?
```bash
# Rebuild without cache
docker-compose up --build --force-recreate
```

### See Python errors?
```bash
# Check Gunicorn logs
docker exec puzzleboss-app tail -100 /var/log/gunicorn/error.log
```

## Next Steps

- Explore the API at http://localhost:5000/apidocs
- Try different puzzle statuses
- Add tags to puzzles
- Test solver assignments
- Check the admin panel at http://localhost/admin.php?assumedid=testuser

## Optional: Enable Features

### Enable BigJimmy Bot (requires Google credentials -- TODO: NOT WORKING YET):
1. Get credentials.json from Google Cloud Console
2. Place in project root
3. Generate token: `docker exec -it puzzleboss-app python gdriveinit.py`
4. Update config in database: `UPDATE config SET val='false' WHERE key='SKIP_GOOGLE_API';`
5. Edit `docker/supervisord.conf`: set `autostart=true` for bigjimmybot
6. Restart: `docker-compose restart app`

### Enable Prometheus Metrics:
Already enabled! Visit http://localhost:5000/metrics

### Enable LLM Queries:
1. Get Gemini API key from Google AI Studio
2. Update config: `UPDATE config SET val='YOUR_KEY' WHERE key='GEMINI_API_KEY';`
3. Test at http://localhost:5000/apidocs (POST /v1/query endpoint)
