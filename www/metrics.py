#!/usr/bin/env python3
import sys
import os
import MySQLdb

# Get the directory containing this script
script_dir = os.path.dirname(os.path.abspath(__file__))
# Get the parent directory by going up one level
parent_dir = os.path.abspath(os.path.join(script_dir, '..'))
# Add the parent directory to the Python path so we can import pblib
sys.path.insert(0, parent_dir)

import pblib
from pblib import *

# Connect to database
conn = MySQLdb.connect(
    host=config['MYSQL']['HOST'],
    user=config['MYSQL']['USERNAME'],
    passwd=config['MYSQL']['PASSWORD'],
    db=config['MYSQL']['DATABASE']
)
cursor = conn.cursor(MySQLdb.cursors.DictCursor)

try:
    # Get activity counts
    cursor.execute("SELECT type, COUNT(*) as count FROM activity GROUP BY type")
    activity_counts = {row['type']: row['count'] for row in cursor.fetchall()}
    
    # Get puzzle status counts
    cursor.execute("SELECT status, COUNT(*) as count FROM puzzle GROUP BY status")
    puzzle_counts = {row['status']: row['count'] for row in cursor.fetchall()}
    
    # Get round counts
    cursor.execute("SELECT COUNT(*) as total FROM round")
    rounds_total = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as solved FROM round WHERE status = 'Solved'")
    rounds_solved = cursor.fetchone()['solved']
    rounds_open = rounds_total - rounds_solved
    
    # Build metrics output
    metrics = []
    
    # Activity metrics
    metrics.extend([
        "# HELP puzzleboss_puzzles_created_total Total number of puzzles created",
        "# TYPE puzzleboss_puzzles_created_total counter",
        f"puzzleboss_puzzles_created_total {activity_counts.get('create', 0)}\n",
        
        "# HELP puzzleboss_puzzles_solved_total Total number of puzzles solved",
        "# TYPE puzzleboss_puzzles_solved_total counter",
        f"puzzleboss_puzzles_solved_total {activity_counts.get('solve', 0)}\n",
        
        "# HELP puzzleboss_comments_made_total Total number of comments made",
        "# TYPE puzzleboss_comments_made_total counter",
        f"puzzleboss_comments_made_total {activity_counts.get('comment', 0)}\n",
        
        "# HELP puzzleboss_assignments_made_total Total number of puzzle assignments made",
        "# TYPE puzzleboss_assignments_made_total counter",
        f"puzzleboss_assignments_made_total {activity_counts.get('interact', 0)}\n"
    ])
    
    # Puzzle status metrics
    metrics.extend([
        "# HELP puzzleboss_puzzles_by_status_total Current number of puzzles in each status",
        "# TYPE puzzleboss_puzzles_by_status_total gauge"
    ])
    
    statuses = ['New', 'Being worked', 'Needs eyes', 'WTF', 'Critical', 'Unnecessary']
    for status in statuses:
        metrics.append(f'puzzleboss_puzzles_by_status_total{{status="{status.lower().replace(" ", "_")}"}} {puzzle_counts.get(status, 0)}')
    
    # Round status metrics
    metrics.extend([
        "\n# HELP puzzleboss_rounds_by_status_total Current number of rounds in each status",
        "# TYPE puzzleboss_rounds_by_status_total gauge",
        f'puzzleboss_rounds_by_status_total{{status="open"}} {rounds_open}',
        f'puzzleboss_rounds_by_status_total{{status="solved"}} {rounds_solved}'
    ])
    
    # Print metrics
    print('\n'.join(metrics))

except Exception as e:
    print(f"Error generating metrics: {str(e)}", file=sys.stderr)
    sys.exit(1)

finally:
    cursor.close()
    conn.close() 