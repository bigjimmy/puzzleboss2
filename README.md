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
    - database access parameters
    - API endpoint access parameters
    - Other config as noted in sample file

- Apache config:
    - www subdir should be a web docroot or alias
    - www subdir should have PHP execution enabled
    - puzzleboss root dir should NOT be accessible via apache
    - User authentication should be configured in apache somehow (we just need the REMOTE_USER header to be set)
    - Optionally proxy into swagger apidocs
    
- MySQL database:
    - Create database for puzzleboss to use (enter name in appropriate puzzleboss.yaml variable)
    - Create user with password for puzzleboss to use, and grant all permissions on above database
    - Import puzzleboss.sql (in scripts subdir) using mysql with the username and database created in above two steps (e.g. `mysql -u puzzleboss puzzleboss < puzzleboss.sql`)
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

- Initial Configuration:
    - Make sure one solver is provisioned via normal account setup procedure and set in privs table to have "puzztech" permissions = YES.
    - Use /pb/admin.php to override the default config values as needed.
    - Alternatively use phpmyadmin or mysql access directly to update config values in the 'config' table in the database.
    - Restart puzzleboss to make new config take effect.
    
- Swagger API Doc:
    - Is accessible at localhost:5000/apidocs (or appropriate proxied URL if behind a proxy) by just running pbapi.py.
    - NOTE: if behind a proxy (e.g. in production), "try it out" functionality of swagger will not work

## Development/Testing Notes:
- For running php frontend without REMOTE_USER setting, Use secret GET params (assumeduser) and the `$noremoteusertestmode = "true";` setting in puzzlebosslib.php and manually insert a "testuser" user into the solvers table of the database.  

- For running without a working puzzcord (discord bot) set the `SKIP_PUZZCORD` config variable to `"true"` in puzzleboss.yaml.

- For running without a google drive, set the `SKIP_GOOGLE_API` config variable to `"true"` in puzzleboss.yaml.
    


