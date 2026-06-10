"""Shared test helpers and global test setup.

conftest.py is imported by pytest before any test module is collected, so the
MySQLdb mock below is in place before test modules do `import pblib`. The unit
test suite runs on a bare runner (CI installs only pytest + pyyaml — no
mysqlclient), and pblib calls refresh_config() at import time, which imports
MySQLdb and reads the config table. Mocking MySQLdb here lets any test module
`import pblib` / `import pbcachelib` directly without its own boilerplate.

The mock is guarded: test modules that set up their own MySQLdb mock (e.g.
test_bigjimmybot, test_rate_limiter, test_pblib_id_types) check
`if 'MySQLdb' not in sys.modules` first, so this does not interfere with them.
"""

import json
import os
import sys
from unittest.mock import MagicMock

# Make the project root importable (pblib, pbcachelib, etc.).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if 'MySQLdb' not in sys.modules:
    _mock_mysqldb = MagicMock()
    _mock_cursor = MagicMock()
    # refresh_config() reads (key, val) rows from the config table.
    _mock_cursor.fetchall.return_value = [
        ("LOGLEVEL", "0"),
    ]
    _mock_conn = MagicMock()
    _mock_conn.cursor.return_value = _mock_cursor
    _mock_mysqldb.connect.return_value = _mock_conn
    _mock_mysqldb.cursors = MagicMock()
    sys.modules['MySQLdb'] = _mock_mysqldb
    sys.modules['MySQLdb.cursors'] = _mock_mysqldb.cursors


# puzzleboss.yaml is gitignored and absent from the CI checkout, but pblib's
# import-time refresh_config() reads it (and sys.exit(255)s on failure). Provide
# a minimal yaml on disk for the test session if it's missing, so test modules
# can `import pblib` directly. Created next to the project root that pblib's
# open("puzzleboss.yaml") resolves against (the test process cwd).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_YAML_PATH = os.path.join(_PROJECT_ROOT, "puzzleboss.yaml")
if not os.path.exists(_YAML_PATH):
    try:
        with open(_YAML_PATH, "w") as _f:
            _f.write(
                "MYSQL:\n  HOST: localhost\n  USERNAME: test\n"
                "  PASSWORD: test\n  DATABASE: test\n"
            )
    except OSError:
        pass  # read-only checkout; tests that need it mock open() themselves


def load_fixture(filename):
    """Load a JSON fixture file."""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', filename)
    with open(fixture_path) as f:
        return json.load(f)
