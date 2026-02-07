#!/usr/bin/env python3

import sys
import os
import yaml
import subprocess
import datetime
import requests
from pathlib import Path

# Get the project root directory (parent of scripts directory)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SCRIPTS_DIR = Path(__file__).parent.resolve()


def debug_log(message):
    """Simple logging function"""
    timestamp = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    print(f"[{timestamp}] {message}", flush=True)


def get_config():
    """Load configuration from yaml file"""
    try:
        with open(PROJECT_ROOT / "puzzleboss.yaml") as f:
            return yaml.load(f, Loader=yaml.FullLoader)
    except Exception as e:
        print(f"Error loading puzzleboss.yaml: {e}")
        sys.exit(1)


def check_backup_permissions(backups_dir: Path) -> bool:
    """Check if we have write permissions for the backup directory"""
    try:
        # Check if directory exists and is writable
        if backups_dir.exists():
            if not os.access(backups_dir, os.W_OK):
                print(
                    f"Error: Backup directory {backups_dir} exists but is not writable"
                )
                print("Try running the script with sudo: sudo ./reset-hunt.py")
                return False
        else:
            # Try to create the directory
            backups_dir.mkdir(parents=True, exist_ok=True)
            if not os.access(backups_dir, os.W_OK):
                print(
                    f"Error: Cannot write to newly created backup directory {backups_dir}"
                )
                print("Try running the script with sudo: sudo ./reset-hunt.py")
                return False

        # Test write permission by creating a temporary file
        test_file = backups_dir / ".permission_test"
        try:
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            print(f"Error: Cannot write to backup directory {backups_dir}: {e}")
            print("Try running the script with sudo: sudo ./reset-hunt.py")
            return False

        return True
    except Exception as e:
        print(f"Error checking backup directory permissions: {e}")
        print("Try running the script with sudo: sudo ./reset-hunt.py")
        return False


def is_mysql_client():
    """Detect if mysqldump is MySQL (not MariaDB) client"""
    try:
        result = subprocess.run(
            ["mysqldump", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        # MySQL client will have "MySQL" in version, MariaDB will have "MariaDB"
        return "MariaDB" not in result.stdout
    except Exception:
        # If we can't detect, assume MySQL for backward compatibility
        return True


def run_command(cmd, error_msg):
    """Run a shell command and handle errors"""
    debug_log(f"Running command: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error: {error_msg}")
        print(f"Command output: {e.stderr}")
        return False


def dump_table(config, table_name, output_file):
    """Dump a table using mysqldump"""
    debug_log(f"Dumping {table_name} table to {output_file}")

    cmd = [
        "mysqldump",
        "-h",
        config["MYSQL"]["HOST"],
        "-u",
        config["MYSQL"]["USERNAME"],
        f"-p{config['MYSQL']['PASSWORD']}",
        "--no-tablespaces",
        "--skip-ssl",  # Skip SSL verification for backup operations
    ]

    # Only add --set-gtid-purged for MySQL client (not MariaDB)
    if is_mysql_client():
        cmd.append("--set-gtid-purged=OFF")

    cmd.extend([
        "--add-drop-table",
        config["MYSQL"]["DATABASE"],
        table_name,
        "-r",
        str(output_file),
    ])

    return run_command(cmd, f"Failed to dump table {table_name}")


def dump_full_database(config, output_file):
    """Dump the entire database using mysqldump"""
    debug_log(f"Dumping full database to {output_file}")

    cmd = [
        "mysqldump",
        "-h",
        config["MYSQL"]["HOST"],
        "-u",
        config["MYSQL"]["USERNAME"],
        f"-p{config['MYSQL']['PASSWORD']}",
        "--no-tablespaces",
        "--skip-ssl",  # Skip SSL verification for backup operations
    ]

    # Only add --set-gtid-purged for MySQL client (not MariaDB)
    if is_mysql_client():
        cmd.append("--set-gtid-purged=OFF")

    cmd.extend([
        "--add-drop-database",
        "--databases",
        config["MYSQL"]["DATABASE"],
        "-r",
        str(output_file),
    ])

    return run_command(cmd, "Failed to dump full database")


def drop_all_views(config):
    """Drop all views in the database to avoid DEFINER issues"""
    debug_log("Dropping all views to avoid DEFINER privilege issues")

    cmd = [
        "mysql",
        "-h",
        config["MYSQL"]["HOST"],
        "-u",
        config["MYSQL"]["USERNAME"],
        f"-p{config['MYSQL']['PASSWORD']}",
        "--skip-ssl",
        config["MYSQL"]["DATABASE"],
        "-N",  # No column names
        "-B",  # Batch mode
        "-e",
        "SELECT TABLE_NAME FROM information_schema.VIEWS WHERE TABLE_SCHEMA = DATABASE();"
    ]

    try:
        # Get list of views
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        views = result.stdout.strip().split('\n')
        views = [v.strip() for v in views if v.strip()]

        if not views:
            debug_log("No views to drop")
            return True

        debug_log(f"Found {len(views)} views to drop")

        # Drop each view
        for view in views:
            drop_cmd = [
                "mysql",
                "-h",
                config["MYSQL"]["HOST"],
                "-u",
                config["MYSQL"]["USERNAME"],
                f"-p{config['MYSQL']['PASSWORD']}",
                "--skip-ssl",
                config["MYSQL"]["DATABASE"],
                "-e",
                f"DROP VIEW IF EXISTS `{view}`;"
            ]
            subprocess.run(drop_cmd, capture_output=True, text=True, check=True)
            debug_log(f"Dropped view: {view}")

        return True
    except Exception as e:
        debug_log(f"Warning: Could not drop views: {e}")
        # Don't fail if we can't drop views - the schema load might still work
        return True


def load_sql_file(config, sql_file):
    """Load an SQL file using mysql command"""
    debug_log(f"Loading SQL file: {sql_file}")

    cmd = [
        "mysql",
        "-h",
        config["MYSQL"]["HOST"],
        "-u",
        config["MYSQL"]["USERNAME"],
        f"-p{config['MYSQL']['PASSWORD']}",
        "--skip-ssl",  # Skip SSL verification for restore operations
        config["MYSQL"]["DATABASE"],
    ]

    try:
        # Read the SQL file and strip DEFINER clauses for RDS compatibility
        with open(sql_file, "r") as f:
            sql_content = f.read()

        # Remove DEFINER clauses (common in views/stored procedures)
        # This is necessary for AWS RDS which doesn't grant SYSTEM_USER privilege
        import re
        sql_content = re.sub(r'DEFINER\s*=\s*`[^`]+`@`[^`]+`\s*', '', sql_content, flags=re.IGNORECASE)

        # Execute the modified SQL
        process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, stderr = process.communicate(input=sql_content)

        if process.returncode != 0:
            print(f"Error loading SQL file {sql_file}")
            print(f"Error output: {stderr}")
            return False
        return True
    except Exception as e:
        print(f"Error loading SQL file {sql_file}: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Reset hunt database (DESTRUCTIVE)')
    parser.add_argument(
        '--yes-i-am-sure-i-want-to-destroy-all-data',
        action='store_true',
        help='Bypass interactive confirmation (DANGEROUS - for automated testing only)'
    )
    args = parser.parse_args()

    print("==WARNING!!!===WARNING!!!===WARNING!!!===WARNING==")
    print("")
    print("Hunt reset: This will ERASE ALL PROGRESS AND PUZZLE DATA")
    print("Solver database, tags, and configuration will be preserved")
    print()
    print("DO NOT DO THIS DURING HUNT!")
    print()

    if args.yes_i_am_sure_i_want_to_destroy_all_data:
        print("WARNING: Using --yes-i-am-sure-i-want-to-destroy-all-data flag")
        print("Proceeding with automated reset...")
    else:
        confirmation = input("Enter the phrase IWANTTODESTROYTHEHUNT to continue: ")
        if confirmation != "IWANTTODESTROYTHEHUNT":
            print("ABORTED.")
            sys.exit(2)

    print("OK. You asked for it.")

    # Load configuration
    config = get_config()

    # Create backup directory with timestamp under scripts/backups
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backups_dir = SCRIPTS_DIR / "backups"
    backup_dir = backups_dir / timestamp

    # Check backup directory permissions before proceeding
    if not check_backup_permissions(backups_dir):
        print("Error: Cannot proceed without write access to backup directory")
        sys.exit(1)

    # Create timestamped backup directory
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating backup directory {backup_dir}: {e}")
        sys.exit(1)

    # Create full database backup
    full_backup_file = backup_dir / "full_database_backup.sql"
    if not dump_full_database(config, full_backup_file):
        print("Failed to create full database backup. Aborting.")
        sys.exit(1)

    # Tables to preserve
    preserve_tables = ["solver", "privs", "config", "tag"]

    # Backup tables we want to preserve
    for table in preserve_tables:
        if not dump_table(config, table, backup_dir / f"{table}.sql"):
            print(f"Failed to backup {table} table. Aborting.")
            sys.exit(1)

    # Drop and recreate the entire database to avoid DEFINER privilege issues
    debug_log(f"Dropping and recreating database {config['MYSQL']['DATABASE']}")

    drop_create_cmd = [
        "mysql",
        "-h",
        config["MYSQL"]["HOST"],
        "-u",
        config["MYSQL"]["USERNAME"],
        f"-p{config['MYSQL']['PASSWORD']}",
        "--skip-ssl",
        "-e",
        f"DROP DATABASE IF EXISTS {config['MYSQL']['DATABASE']}; CREATE DATABASE {config['MYSQL']['DATABASE']};"
    ]

    try:
        subprocess.run(drop_create_cmd, capture_output=True, text=True, check=True)
        debug_log("Database dropped and recreated successfully")
    except subprocess.CalledProcessError as e:
        print(f"Error dropping and recreating database: {e.stderr}")
        print("Failed to reset database. Aborting.")
        sys.exit(1)

    # Load schema into fresh database
    schema_file = SCRIPTS_DIR / "puzzleboss.sql"
    if not schema_file.exists():
        print("Cannot find puzzleboss.sql schema file. Aborting.")
        sys.exit(1)

    # Load all tables using schema (DEFINER clauses will be stripped automatically)
    if not load_sql_file(config, schema_file):
        print("Failed to load schema. Aborting.")
        sys.exit(1)

    # Restore preserved tables
    for table in preserve_tables:
        if not load_sql_file(config, backup_dir / f"{table}.sql"):
            print(f"Failed to restore {table} table. Aborting.")
            sys.exit(1)

    # Invalidate cache
    debug_log("Invalidating cache...")
    try:
        api_base = config.get("API", {}).get("APIURI", "http://localhost:5000")
        resp = requests.post(f"{api_base}/cache/invalidate", timeout=10)
        if resp.ok:
            debug_log("Cache invalidated successfully")
        else:
            debug_log(f"Warning: Cache invalidation returned status {resp.status_code}")
    except Exception as e:
        debug_log(f"Warning: Could not invalidate cache: {e}")
        debug_log("You may need to restart the API server or wait for cache to expire")

    print("\nHunt reset completed successfully!")
    print(f"Backups saved in: {backup_dir}")
    print(f"Full database backup: {full_backup_file}")


if __name__ == "__main__":
    main()
