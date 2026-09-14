#!/usr/bin/env python3
"""
Unit tests for the security/reliability hardening in pblib:

1. update_puzzle_field rejects non-schema field names (SQL identifier
   allowlist) instead of interpolating them into the UPDATE statement.
2. ALLOW_USERNAME_OVERRIDE is honored only from puzzleboss.yaml — the DB
   config-table row can never enable it.
3. refresh_config raises on failure instead of sys.exit(255)ing, so
   periodic refreshes (maybe_refresh_config) keep serving stale config.

Run with: pytest tests/test_security_fixes.py -v
"""

import os
import sys
from unittest.mock import MagicMock, patch, mock_open

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if 'MySQLdb' not in sys.modules or isinstance(sys.modules.get('MySQLdb'), MagicMock):
    mock_mysqldb = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [("LOGLEVEL", "0")]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_mysqldb.connect.return_value = mock_conn
    mock_mysqldb.cursors = MagicMock()
    sys.modules['MySQLdb'] = mock_mysqldb
    sys.modules['MySQLdb.cursors'] = mock_mysqldb.cursors

_yaml_config = """
MYSQL:
  HOST: localhost
  USERNAME: test
  PASSWORD: test
  DATABASE: test
"""

if 'pblib' not in sys.modules:
    with patch('builtins.open', mock_open(read_data=_yaml_config)):
        import pblib
else:
    pblib = sys.modules['pblib']

pblib.configstruct.setdefault("LOGLEVEL", "0")


def _make_conn():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


class TestUpdatePuzzleFieldAllowlist:
    """update_puzzle_field must refuse to interpolate non-schema identifiers."""

    @patch('pblib.debug_log')
    def test_valid_field_updates(self, mock_log):
        conn, cursor = _make_conn()
        pblib.update_puzzle_field(287, "xyzloc", "table 3", conn)
        sql = cursor.execute.call_args_list[0][0][0]
        assert "UPDATE puzzle SET xyzloc" in sql

    @patch('pblib.debug_log')
    @pytest.mark.parametrize("field", [
        "id",                              # deliberately excluded
        "round",                           # not a puzzle column
        "status = 'Solved', answer",       # injection attempt
        "name; DROP TABLE puzzle; --",
    ])
    def test_invalid_field_raises_without_sql(self, mock_log, field):
        conn, cursor = _make_conn()
        with pytest.raises(ValueError):
            pblib.update_puzzle_field(287, field, "x", conn)
        cursor.execute.assert_not_called()

    def test_allowlist_covers_structural_fields(self):
        # Every structural field must be updatable, or invalidation is dead code.
        assert pblib.STRUCTURAL_PUZZLE_FIELDS <= pblib.PUZZLE_UPDATABLE_COLUMNS

    def test_allowlist_excludes_id(self):
        assert "id" not in pblib.PUZZLE_UPDATABLE_COLUMNS


class TestAllowUsernameOverrideYamlOnly:
    """ALLOW_USERNAME_OVERRIDE comes from puzzleboss.yaml, never the DB."""

    @pytest.mark.parametrize("yaml_val,expected", [
        ("true", "true"),
        (True, "true"),
        ("false", "false"),
        ("TRUE", "true"),
        (None, "false"),
        ("yes", "false"),  # only literal true counts
    ])
    def test_yaml_value_normalization(self, yaml_val, expected):
        with patch.object(pblib, 'config', {"ALLOW_USERNAME_OVERRIDE": yaml_val}):
            assert pblib.yaml_allow_username_override() == expected

    def test_absent_key_is_false(self):
        with patch.object(pblib, 'config', {"MYSQL": {}}):
            assert pblib.yaml_allow_username_override() == "false"

    @patch('pblib.debug_log')
    def test_db_row_cannot_enable_override(self, mock_log):
        """A config-table row of 'true' must not survive refresh_config when
        the YAML doesn't set the key."""
        db_rows = [("LOGLEVEL", "0"), ("ALLOW_USERNAME_OVERRIDE", "true")]
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = db_rows
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch('builtins.open', mock_open(read_data=_yaml_config)), \
             patch.object(pblib.MySQLdb, 'connect', return_value=mock_conn):
            pblib.refresh_config()
        assert pblib.configstruct["ALLOW_USERNAME_OVERRIDE"] == "false"


class TestRefreshConfigNonFatal:
    """refresh_config raises (rather than exits) so callers decide fatality."""

    @patch('pblib.debug_log')
    def test_yaml_failure_raises_not_exits(self, mock_log):
        with patch('builtins.open', side_effect=OSError("no yaml")):
            with pytest.raises(OSError):
                pblib.refresh_config()

    @patch('pblib.debug_log')
    def test_db_failure_raises_not_exits(self, mock_log):
        with patch('builtins.open', mock_open(read_data=_yaml_config)), \
             patch.object(pblib.MySQLdb, 'connect', side_effect=RuntimeError("db down")):
            with pytest.raises(RuntimeError):
                pblib.refresh_config()

    @patch('pblib.debug_log')
    def test_maybe_refresh_config_swallows_failure(self, mock_log):
        """Periodic refresh failures must not propagate — stale config keeps
        serving. This is the worker-survival guarantee."""
        pblib._last_config_refresh = None  # force a refresh attempt
        with patch.object(pblib, 'refresh_config', side_effect=RuntimeError("db down")):
            pblib.maybe_refresh_config()  # must not raise
        warned = any(call[0][0] == 2 for call in mock_log.call_args_list)
        assert warned, "expected a SEV2 warning for the failed refresh"
