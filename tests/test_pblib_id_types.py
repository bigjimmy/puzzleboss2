#!/usr/bin/env python3
"""
Unit tests for ID type normalization across all pblib functions.

All database ID columns (puzzle.id, solver.id, round.id, activity.id) are
INT(11) in MySQL.  Every pblib function that accepts an ID parameter must
normalize it to int() at the boundary, so callers can pass either int or
string and get consistent behavior.

This test file verifies that:
1. Every pblib function accepts both int and string ID parameters
2. The int() normalization produces correct SQL parameters
3. JSON structures always contain integer IDs (not string)

Run with: pytest tests/test_pblib_id_types.py -v
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch, mock_open

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pblib calls refresh_config() at module level, which requires:
# 1. MySQLdb (for DB config)
# 2. puzzleboss.yaml (for YAML config)
# 3. A working MySQL connection (for config table)

if 'MySQLdb' not in sys.modules or isinstance(sys.modules.get('MySQLdb'), MagicMock):
    mock_mysqldb = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("LOGLEVEL", "0"),
        ("BIGJIMMY_AUTOASSIGN", "true"),
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_mysqldb.connect.return_value = mock_conn
    mock_mysqldb.cursors = MagicMock()
    sys.modules['MySQLdb'] = mock_mysqldb
    sys.modules['MySQLdb.cursors'] = mock_mysqldb.cursors

if 'pblib' in sys.modules and isinstance(sys.modules['pblib'], MagicMock):
    del sys.modules['pblib']

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
    """Create a mock DB connection with DictCursor-style behavior."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


class TestCheckRoundCompletionIdType:
    """check_round_completion() must accept both int and string round_id."""

    @patch('pblib.debug_log')
    def test_string_round_id(self, mock_log):
        conn, cursor = _make_conn()
        cursor.fetchone.return_value = {"total": 1, "solved": 1}

        pblib.check_round_completion("42", conn)

        # Verify the SQL parameter is int, not string
        execute_calls = cursor.execute.call_args_list
        assert len(execute_calls) >= 1
        first_call_params = execute_calls[0][0][1]
        assert first_call_params == (42,), f"Expected (42,), got {first_call_params}"

    @patch('pblib.debug_log')
    def test_int_round_id(self, mock_log):
        conn, cursor = _make_conn()
        cursor.fetchone.return_value = {"total": 1, "solved": 1}

        pblib.check_round_completion(42, conn)

        execute_calls = cursor.execute.call_args_list
        first_call_params = execute_calls[0][0][1]
        assert first_call_params == (42,)


class TestClearPuzzleSolversIdType:
    """clear_puzzle_solvers() must accept both int and string puzzle_id."""

    @patch('pblib.debug_log')
    def test_string_puzzle_id(self, mock_log):
        conn, cursor = _make_conn()

        pblib.clear_puzzle_solvers("287", conn)

        # First execute call is the UPDATE — verify the SQL parameter is int
        execute_calls = cursor.execute.call_args_list
        assert len(execute_calls) >= 1
        params = execute_calls[0][0][1]
        assert params == (287,), f"Expected (287,), got {params}"

    @patch('pblib.debug_log')
    def test_int_puzzle_id(self, mock_log):
        conn, cursor = _make_conn()

        pblib.clear_puzzle_solvers(287, conn)

        execute_calls = cursor.execute.call_args_list
        params = execute_calls[0][0][1]
        assert params == (287,)


class TestLogActivityIdType:
    """log_activity() must accept both int and string for puzzle_id and solver_id."""

    @patch('pblib.debug_log')
    def test_string_ids(self, mock_log):
        conn, cursor = _make_conn()

        pblib.log_activity("287", "create", "101", "puzzleboss", conn)

        execute_calls = cursor.execute.call_args_list
        assert len(execute_calls) == 1
        params = execute_calls[0][0][1]
        # Should be (287, 101, 'puzzleboss', 'create')
        assert params[0] == 287, f"puzzle_id should be int 287, got {params[0]!r}"
        assert params[1] == 101, f"solver_id should be int 101, got {params[1]!r}"
        assert isinstance(params[0], int)
        assert isinstance(params[1], int)

    @patch('pblib.debug_log')
    def test_int_ids(self, mock_log):
        conn, cursor = _make_conn()

        pblib.log_activity(287, "create", 101, "puzzleboss", conn)

        params = cursor.execute.call_args_list[0][0][1]
        assert params[0] == 287
        assert params[1] == 101
        assert isinstance(params[0], int)
        assert isinstance(params[1], int)

    @patch('pblib.debug_log')
    def test_with_timestamp_string_ids(self, mock_log):
        conn, cursor = _make_conn()

        pblib.log_activity("287", "revise", "101", "bigjimmybot", conn, timestamp=1700000000)

        params = cursor.execute.call_args_list[0][0][1]
        assert params[0] == 287
        assert params[1] == 101
        assert isinstance(params[0], int)
        assert isinstance(params[1], int)


class TestUpdatePuzzleFieldIdType:
    """update_puzzle_field() must accept both int and string puzzle_id."""

    @patch('pblib.debug_log')
    def test_string_puzzle_id_direct_field(self, mock_log):
        conn, cursor = _make_conn()

        pblib.update_puzzle_field("287", "status", "Solved", conn)

        # First execute call is the UPDATE — verify the SQL parameter is int
        execute_calls = cursor.execute.call_args_list
        assert len(execute_calls) >= 1
        params = execute_calls[0][0][1]
        # Should be ('Solved', 287) — value first, then puzzle_id in WHERE
        assert params[1] == 287, f"puzzle_id should be int 287, got {params[1]!r}"
        assert isinstance(params[1], int)

    @patch('pblib.debug_log')
    def test_string_puzzle_id_solver_assignment(self, mock_log):
        """update_puzzle_field with field='solvers' delegates to assign_solver_to_puzzle."""
        conn, cursor = _make_conn()
        # Mock the assign path: fetchall returns [] (no current puzzle), fetchone for current_solvers + history
        cursor.fetchall.return_value = []
        fetchone_count = {"n": 0}

        def mock_fetchone():
            fetchone_count["n"] += 1
            if fetchone_count["n"] == 1:
                return {"current_solvers": json.dumps({"solvers": []}), "status": "Being worked"}
            elif fetchone_count["n"] == 2:
                return {"solver_history": json.dumps({"solvers": []})}
            return None

        cursor.fetchone = mock_fetchone

        pblib.update_puzzle_field("287", "solvers", "101", conn)

        # Verify the JSON stored has int solver_id
        update_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c)
        ]
        assert len(update_calls) >= 1
        stored_json = update_calls[0][0][1][0]
        stored = json.loads(stored_json)
        assert stored["solvers"][0]["solver_id"] == 101
        assert isinstance(stored["solvers"][0]["solver_id"], int)


class TestGetSolverByIdFromDbIdType:
    """get_solver_by_id_from_db() must accept both int and string solver_id."""

    @patch('pblib.debug_log')
    def test_string_solver_id(self, mock_log):
        conn, cursor = _make_conn()
        cursor.fetchone.return_value = {"id": 101, "name": "testuser"}

        # Need to mock get_last_activity_for_solver since it's called internally
        with patch.object(pblib, 'get_last_activity_for_solver', return_value=None):
            result = pblib.get_solver_by_id_from_db("101", conn)

        # Verify the SQL parameter is int
        params = cursor.execute.call_args_list[0][0][1]
        assert params == (101,), f"Expected (101,), got {params}"

    @patch('pblib.debug_log')
    def test_int_solver_id(self, mock_log):
        conn, cursor = _make_conn()
        cursor.fetchone.return_value = {"id": 101, "name": "testuser"}

        with patch.object(pblib, 'get_last_activity_for_solver', return_value=None):
            result = pblib.get_solver_by_id_from_db(101, conn)

        params = cursor.execute.call_args_list[0][0][1]
        assert params == (101,)


class TestGetLastActivityForSolverIdType:
    """get_last_activity_for_solver() must accept both int and string solver_id."""

    @patch('pblib.debug_log')
    def test_string_solver_id(self, mock_log):
        conn, cursor = _make_conn()
        cursor.fetchone.return_value = None

        pblib.get_last_activity_for_solver("101", conn)

        params = cursor.execute.call_args_list[0][0][1]
        assert params == (101,), f"Expected (101,), got {params}"

    @patch('pblib.debug_log')
    def test_int_solver_id(self, mock_log):
        conn, cursor = _make_conn()
        cursor.fetchone.return_value = None

        pblib.get_last_activity_for_solver(101, conn)

        params = cursor.execute.call_args_list[0][0][1]
        assert params == (101,)


class TestGetLastSheetActivityForPuzzleIdType:
    """get_last_sheet_activity_for_puzzle() must accept both int and string puzzle_id."""

    @patch('pblib.debug_log')
    def test_string_puzzle_id(self, mock_log):
        conn, cursor = _make_conn()
        cursor.fetchone.return_value = None

        pblib.get_last_sheet_activity_for_puzzle("287", conn)

        params = cursor.execute.call_args_list[0][0][1]
        assert params == (287,), f"Expected (287,), got {params}"

    @patch('pblib.debug_log')
    def test_int_puzzle_id(self, mock_log):
        conn, cursor = _make_conn()
        cursor.fetchone.return_value = None

        pblib.get_last_sheet_activity_for_puzzle(287, conn)

        params = cursor.execute.call_args_list[0][0][1]
        assert params == (287,)


class TestGetLastActivityForPuzzleIdType:
    """get_last_activity_for_puzzle() must accept both int and string puzzle_id."""

    @patch('pblib.debug_log')
    def test_string_puzzle_id(self, mock_log):
        conn, cursor = _make_conn()
        cursor.fetchone.return_value = None

        pblib.get_last_activity_for_puzzle("287", conn)

        params = cursor.execute.call_args_list[0][0][1]
        assert params == (287,), f"Expected (287,), got {params}"

    @patch('pblib.debug_log')
    def test_int_puzzle_id(self, mock_log):
        conn, cursor = _make_conn()
        cursor.fetchone.return_value = None

        pblib.get_last_activity_for_puzzle(287, conn)

        params = cursor.execute.call_args_list[0][0][1]
        assert params == (287,)



# NOTE: Assign/unassign JSON integrity tests (int storage in current_solvers
# and solver_history) live in test_pblib_solver_assignment.py to avoid
# duplication.  This file focuses on int() normalization at function boundaries.
