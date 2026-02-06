#!/usr/bin/env python3
"""
Fix STATUS_METADATA in production database with proper emoji encoding.
Run this on your production server.
"""

import MySQLdb
import json
import yaml

# Load database config
with open('../puzzleboss.yaml', 'r') as f:
    config = yaml.safe_load(f)

db_config = config['MYSQL']

# Status metadata with emojis
status_metadata = [
    {"name": "WTF", "emoji": "☢️", "text": "?", "order": 0},
    {"name": "Critical", "emoji": "⚠️", "text": "!", "order": 1},
    {"name": "Needs eyes", "emoji": "👀", "text": "E", "order": 2},
    {"name": "Being worked", "emoji": "🙇", "text": "W", "order": 3},
    {"name": "Speculative", "emoji": "🔮", "text": "S", "order": 4},
    {"name": "Under control", "emoji": "🤝", "text": "U", "order": 5},
    {"name": "New", "emoji": "🆕", "text": "N", "order": 6},
    {"name": "Grind", "emoji": "⛏️", "text": "G", "order": 7},
    {"name": "Waiting for HQ", "emoji": "⌛", "text": "H", "order": 8},
    {"name": "Abandoned", "emoji": "🏳️", "text": "A", "order": 9},
    {"name": "Solved", "emoji": "✅", "text": "*", "order": 10},
    {"name": "Unnecessary", "emoji": "🙃", "text": "X", "order": 11},
    {"name": "[hidden]", "emoji": "👻", "text": "H", "order": 99}
]

# Convert to JSON
json_str = json.dumps(status_metadata, ensure_ascii=False)

print("Connecting to database...")
conn = MySQLdb.connect(
    host=db_config['HOST'],
    port=db_config.get('PORT', 3306),
    user=db_config['USERNAME'],
    passwd=db_config['PASSWORD'],
    db=db_config['DATABASE'],
    charset='utf8mb4',
    use_unicode=True
)

cursor = conn.cursor()

# Ensure connection is using utf8mb4
cursor.execute("SET NAMES utf8mb4")
cursor.execute("SET CHARACTER SET utf8mb4")
cursor.execute("SET character_set_connection=utf8mb4")

# Check and fix table encoding if needed
print("Checking config table encoding...")
cursor.execute("""
    SELECT CHARACTER_SET_NAME, COLLATION_NAME
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'config' AND COLUMN_NAME = 'val'
""", (db_config['DATABASE'],))
charset_info = cursor.fetchone()
if charset_info:
    print(f"  Current: {charset_info[0]} / {charset_info[1]}")
    if charset_info[0] != 'utf8mb4':
        print("  Converting table to utf8mb4...")
        cursor.execute("ALTER TABLE config CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
        print("  ✅ Table converted")

print(f"Updating STATUS_METADATA with {len(status_metadata)} statuses...")
cursor.execute(
    "UPDATE config SET val = %s WHERE `key` = 'STATUS_METADATA'",
    (json_str,)
)
conn.commit()

# Verify
cursor.execute("SELECT val FROM config WHERE `key` = 'STATUS_METADATA'")
result = cursor.fetchone()
if result:
    loaded = json.loads(result[0])
    print(f"\n✅ Success! Updated {len(loaded)} statuses:")
    for s in loaded:
        print(f"  {s['order']:2d}. {s['name']:20s} {s['emoji']} ({s['text']})")
else:
    print("❌ ERROR: Could not verify update")

cursor.close()
conn.close()

print("\n🔄 Now restart your Flask API service:")
print("   sudo systemctl restart puzzleboss2")
