#!/usr/bin/env python3

import sys
import os
import yaml
import subprocess
import datetime
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
                print(f"Error: Backup directory {backups_dir} exists but is not writable")
                return False
        else:
            # Try to create the directory
            backups_dir.mkdir(parents=True, exist_ok=True)
            if not os.access(backups_dir, os.W_OK):
                print(f"Error: Cannot write to newly created backup directory {backups_dir}")
                return False
        
        # Test write permission by creating a temporary file
        test_file = backups_dir / ".permission_test"
        try:
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            print(f"Error: Cannot write to backup directory {backups_dir}: {e}")
            return False
            
        return True
    except Exception as e:
        print(f"Error checking backup directory permissions: {e}")
        return False

def run_command(cmd, error_msg):
    """Run a shell command and handle errors"""
    debug_log(f"Running command: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
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
        "-h", config["MYSQL"]["HOST"],
        "-u", config["MYSQL"]["USERNAME"],
        f"-p{config['MYSQL']['PASSWORD']}",
        "--no-tablespaces",
        "--set-gtid-purged=OFF",
        "--add-drop-table",
        config["MYSQL"]["DATABASE"],
        table_name,
        "-r", str(output_file)
    ]
    
    return run_command(cmd, f"Failed to dump table {table_name}")

def dump_full_database(config, output_file):
    """Dump the entire database using mysqldump"""
    debug_log(f"Dumping full database to {output_file}")
    
    cmd = [
        "mysqldump",
        "-h", config["MYSQL"]["HOST"],
        "-u", config["MYSQL"]["USERNAME"],
        f"-p{config['MYSQL']['PASSWORD']}",
        "--no-tablespaces",
        "--set-gtid-purged=OFF",
        "--add-drop-database",
        "--databases",
        config["MYSQL"]["DATABASE"],
        "-r", str(output_file)
    ]
    
    return run_command(cmd, "Failed to dump full database")

def load_sql_file(config, sql_file):
    """Load an SQL file using mysql command"""
    debug_log(f"Loading SQL file: {sql_file}")
    
    cmd = [
        "mysql",
        "-h", config["MYSQL"]["HOST"],
        "-u", config["MYSQL"]["USERNAME"],
        f"-p{config['MYSQL']['PASSWORD']}",
        config["MYSQL"]["DATABASE"]
    ]
    
    try:
        with open(sql_file, 'r') as f:
            process = subprocess.Popen(cmd, stdin=f, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                print(f"Error loading SQL file {sql_file}")
                print(f"Error output: {stderr}")
                return False
            return True
    except Exception as e:
        print(f"Error loading SQL file {sql_file}: {e}")
        return False

def main():
    print("==WARNING!!!===WARNING!!!===WARNING!!!===WARNING==")
    print("")
    print("Hunt reset: This will ERASE ALL PROGRESS AND PUZZLE DATA")
    print("Solver ID/discord database will be preserved")
    print()
    print("DO NOT DO THIS DURING HUNT!")
    print()
    
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
    preserve_tables = ['solver', 'privs', 'config']
    
    # Backup tables we want to preserve
    for table in preserve_tables:
        if not dump_table(config, table, backup_dir / f"{table}.sql"):
            print(f"Failed to backup {table} table. Aborting.")
            sys.exit(1)
    
    # Drop and recreate database using schema
    schema_file = SCRIPTS_DIR / "puzzleboss.sql"
    if not schema_file.exists():
        print("Cannot find puzzleboss.sql schema file. Aborting.")
        sys.exit(1)
    
    # Drop and recreate all tables using schema
    if not load_sql_file(config, schema_file):
        print("Failed to load schema. Aborting.")
        sys.exit(1)
    
    # Restore preserved tables
    for table in preserve_tables:
        if not load_sql_file(config, backup_dir / f"{table}.sql"):
            print(f"Failed to restore {table} table. Aborting.")
            sys.exit(1)
    
    print("\nHunt reset completed successfully!")
    print(f"Backups saved in: {backup_dir}")
    print(f"Full database backup: {full_backup_file}")

if __name__ == "__main__":
    main() 