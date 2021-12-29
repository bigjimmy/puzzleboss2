#Puzzleboss 2000
---

**Description**: Puzzle solving team backend and interface developed by ATTORNEY for mystery hunts.

**Owner**: Benjamin O'Connor (benoc@alum.mit.edu)

## Setup:

- git clone onto server
- Server-side prerequisites:
    - php
    - python >= 3.8
    - Apache (see below for config)
    - MySQL (see below for schema load and config instructions)
    
- copy puzzleboss-SAMPLE.yaml into puzzleboss.yaml and edit appropriately:
    - LOGLEVELs: 0 = FATAL, 1=CRIT, 2=WARN, 3=INFO, 4=DEBUG, 5=TRACE
    - BIN_URI: URI root for web-accessible tools, forms, pages (where www subdir will be reachable publically)
    - The rest should be self explanatory

- Apache config:
    - www subdir should be a web docroot or alias
    - www subdir should have PHP execution enabled
    - puzzleboss root dir should NOT be accessible via apache
    - User authentication should be configured in apache somehow (we just need the REMOTE_USER header to be set)
    - Optionally proxy into swagger apidocs
    
- MySQL database:
    - Create database for puzzleboss to use (enter name in appropriate puzzleboss.yaml variable)
    - Create user with password for puzzleboss to use, and grant all permissions on above database
    - Import puzzleboss.sql (in scripts subdir) using mysql with the username and database created in above two steps
    - IMPORTANT:  above step will destroy previous database.  If you'd like to preserve solvers table, use the reset-hunt script.
    
- Google Sheets Setup:
    - Set up the app authentication as documented by google, to get a `credentials.json` file. Place it in top level directory.
    - Run gdriveinit.py and follow instructions to authenticate with google and automatically generate `token.json`
    - You may need to run the above two steps on a workstation with a modern web browser
    - Pick name of folder for app to create (or an existing one that will be used) for google docs and place it in puzzleboss.yaml
    - All google sheets related ops can be disabled (e.g. for dev testing) via variable in puzzleboss.yaml

- Running the REST Api Service:
    - Start up pbrest.py: Will run on localhost:5000. 
    - For actual multi-client use, install gunicorn and use the wsgi.py app object provided. Is safe to run on multiple servers at once for scale.
    
- Swagger API Doc:
    - Is accessible at localhost:5000/apidocs (or appropriate proxied URL if behind a proxy) by just running pbapi.py.
    - NOTE: if behind a proxy (e.g. in production), "try it out" functionality of swagger will not work

## Development/Testing Notes:
- For running php frontend without REMOTE_USER setting, Use secret GET params (assumeduser) and the `$noremoteusertestmode = "true";` setting in puzzlebosslib.php.

- For running without a working puzzcord (discord bot) set the `SKIP_PUZZCORD` config variable to `"true"` in puzzleboss.yaml.

- For running without a google drive, set the `SKIP_GOOGLE_API` config variable to `"true"` in puzzleboss.yaml.
    


