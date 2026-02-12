#!/usr/bin/env python3
"""
Unit tests for pblib solver assignment functions.

Focuses on the type normalization boundary: solver_id can arrive as
int (from bigjimmybot/MySQL DictCursor) or str (from Flask URL params).
Both paths must produce consistent JSON in current_solvers/solver_history.

Run with: pytest tests/test_pblib_solver_assignment.py -v
"""

import pytest
import json
import os
import sys
import importlib
from unittest.mock import MagicMock, patch, mock_open

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pblib calls refresh_config() at module level, which requires:
# 1. MySQLdb (for DB config)
# 2. puzzleboss.yaml (for YAML config)
# 3. A working MySQL connection (for config table)
#
# When running in pytest, pblib may already be loaded (as a MagicMock from
# bigjimmybot tests, or as the real module if running standalone). Handle both.

if 'MySQLdb' not in sys.modules or isinstance(sys.modules.get('MySQLdb'), MagicMock):
    mock_mysqldb = MagicMock()
    # Make cursor.fetchall() return config rows as tuples (key, value)
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

# If pblib was loaded as a MagicMock by bigjimmybot tests, remove it
if 'pblib' in sys.modules and isinstance(sys.modules['pblib'], MagicMock):
    del sys.modules['pblib']

# Create a minimal YAML config file mock for pblib's refresh_config
_yaml_config = """
MYSQL:
  HOST: localhost
  USERNAME: test
  PASSWORD: test
  DATABASE: test
"""

# Import pblib with mocked YAML file
if 'pblib' not in sys.modules:
    with patch('builtins.open', mock_open(read_data=_yaml_config)):
        import pblib
else:
    pblib = sys.modules['pblib']

# Ensure configstruct has LOGLEVEL so debug_log doesn't crash
pblib.configstruct.setdefault("LOGLEVEL", "0")

from pblib import assign_solver_to_puzzle, unassign_solver_from_puzzle


def _make_mock_conn(current_solvers_json=None, solver_history_json=None):
    """Create a mock DB connection that simulates puzzle JSON columns.

    The mock cursor returns appropriate values for the SELECT queries
    in assign/unassign functions, and tracks UPDATE calls.
    """
    if current_solvers_json is None:
        current_solvers_json = json.dumps({"solvers": []})
    if solver_history_json is None:
        solver_history_json = json.dumps({"solvers": []})

    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor

    # Track what queries have been executed so we can return different
    # results for different SELECT queries
    fetchone_count = {"n": 0}

    # Call sequence in assign_solver_to_puzzle:
    # 1. JSON_SEARCH lookup for current puzzle → fetchall (returns [] = not assigned)
    # 2. SELECT current_solvers → fetchone
    # 3. SELECT solver_history → fetchone
    cursor.fetchall.return_value = []  # Not currently assigned to any puzzle

    def mock_fetchone():
        fetchone_count["n"] += 1
        n = fetchone_count["n"]
        if n == 1:
            return {"current_solvers": current_solvers_json}
        elif n == 2:
            return {"solver_history": solver_history_json}
        return None

    cursor.fetchone = mock_fetchone

    return conn, cursor


class TestAssignSolverTypeNormalization:
    """Test that solver_id type (int vs str) is handled consistently."""

    @patch('pblib.debug_log')
    def test_string_solver_id_stored_as_int(self, mock_log):
        """String solver_id from Flask route should be stored as int in JSON."""
        conn, cursor = _make_mock_conn()

        assign_solver_to_puzzle("287", "101", conn)

        # Find the UPDATE current_solvers call
        update_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c)
        ]
        assert len(update_calls) >= 1, "Expected UPDATE current_solvers call"

        # Extract the JSON that was written
        stored_json = update_calls[0][0][1][0]  # First positional arg tuple, first element
        stored = json.loads(stored_json)
        assert stored["solvers"][0]["solver_id"] == 101  # int, not "101"
        assert isinstance(stored["solvers"][0]["solver_id"], int)

    @patch('pblib.debug_log')
    def test_int_solver_id_stored_as_int(self, mock_log):
        """Int solver_id from bigjimmybot should be stored as int in JSON."""
        conn, cursor = _make_mock_conn()

        assign_solver_to_puzzle(287, 101, conn)

        update_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c)
        ]
        assert len(update_calls) >= 1
        stored_json = update_calls[0][0][1][0]
        stored = json.loads(stored_json)
        assert stored["solvers"][0]["solver_id"] == 101
        assert isinstance(stored["solvers"][0]["solver_id"], int)

    @patch('pblib.debug_log')
    def test_no_duplicate_when_string_matches_existing_int(self, mock_log):
        """Assigning with string "101" should not duplicate existing int 101."""
        existing = json.dumps({"solvers": [{"solver_id": 101}]})
        conn, cursor = _make_mock_conn(current_solvers_json=existing)

        assign_solver_to_puzzle("287", "101", conn)

        # Should NOT have an UPDATE current_solvers call (already present)
        update_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c)
        ]
        assert len(update_calls) == 0, "Should not duplicate solver in current_solvers"

    @patch('pblib.debug_log')
    def test_no_duplicate_when_int_matches_existing_string(self, mock_log):
        """Assigning with int 101 should not duplicate existing string "101"."""
        existing = json.dumps({"solvers": [{"solver_id": "101"}]})
        conn, cursor = _make_mock_conn(current_solvers_json=existing)

        assign_solver_to_puzzle(287, 101, conn)

        update_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c)
        ]
        assert len(update_calls) == 0, "Should not duplicate solver in current_solvers"


class TestUnassignSolverTypeNormalization:
    """Test that unassign handles int/string solver_id correctly."""

    @patch('pblib.debug_log')
    def test_string_id_removes_int_entry(self, mock_log):
        """String solver_id "101" should remove int entry 101."""
        existing = json.dumps({"solvers": [{"solver_id": 101}]})
        conn, cursor = _make_mock_conn(current_solvers_json=existing)

        # Mock fetchone for unassign (only one SELECT)
        cursor.fetchone = lambda: {"current_solvers": existing}

        unassign_solver_from_puzzle("287", "101", conn)

        update_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c)
        ]
        assert len(update_calls) == 1
        stored_json = update_calls[0][0][1][0]
        stored = json.loads(stored_json)
        assert len(stored["solvers"]) == 0, "Solver should have been removed"

    @patch('pblib.debug_log')
    def test_int_id_removes_string_entry(self, mock_log):
        """Int solver_id 101 should remove legacy string entry "101"."""
        existing = json.dumps({"solvers": [{"solver_id": "101"}]})
        conn, cursor = _make_mock_conn(current_solvers_json=existing)

        cursor.fetchone = lambda: {"current_solvers": existing}

        unassign_solver_from_puzzle(287, 101, conn)

        update_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c)
        ]
        assert len(update_calls) == 1
        stored_json = update_calls[0][0][1][0]
        stored = json.loads(stored_json)
        assert len(stored["solvers"]) == 0, "Legacy string solver should have been removed"

    @patch('pblib.debug_log')
    def test_unassign_preserves_other_solvers(self, mock_log):
        """Unassigning one solver should not affect others."""
        existing = json.dumps({"solvers": [
            {"solver_id": 101},
            {"solver_id": 202},
            {"solver_id": 303},
        ]})
        conn, cursor = _make_mock_conn(current_solvers_json=existing)

        cursor.fetchone = lambda: {"current_solvers": existing}

        unassign_solver_from_puzzle(287, 202, conn)

        update_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c)
        ]
        stored_json = update_calls[0][0][1][0]
        stored = json.loads(stored_json)
        remaining_ids = [s["solver_id"] for s in stored["solvers"]]
        assert remaining_ids == [101, 303]


class TestAssignUnassignsFromOldPuzzle:
    """Test that assigning to a new puzzle unassigns from old puzzles."""

    @patch('pblib.debug_log')
    def test_unassign_from_old_puzzle_with_legacy_string_id(self, mock_log):
        """Assigning solver should unassign from old puzzle even if stored as string."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor

        fetchone_count = {"n": 0}

        # fetchall returns old puzzle (id=284) with solver on it
        cursor.fetchall.return_value = [{"id": 284}]

        def mock_fetchone():
            fetchone_count["n"] += 1
            n = fetchone_count["n"]
            # Calls:
            # 1. unassign_solver_from_puzzle SELECT current_solvers for puzzle 284
            # 2. assign: SELECT current_solvers for puzzle 287
            # 3. assign: SELECT solver_history for puzzle 287
            if n == 1:
                # Old puzzle has solver stored as string (legacy)
                return {"current_solvers": json.dumps({"solvers": [{"solver_id": "101"}]})}
            elif n == 2:
                return {"current_solvers": json.dumps({"solvers": []})}
            elif n == 3:
                return {"solver_history": json.dumps({"solvers": []})}
            return None

        cursor.fetchone = mock_fetchone

        assign_solver_to_puzzle(287, 101, conn)

        # Verify the unassign UPDATE was called for puzzle 284
        unassign_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c) and '284' in str(c)
        ]
        assert len(unassign_calls) >= 1, "Should unassign from old puzzle 284"
        stored_json = unassign_calls[0][0][1][0]
        stored = json.loads(stored_json)
        assert len(stored["solvers"]) == 0, "Old puzzle should have no solvers"

    @patch('pblib.debug_log')
    def test_unassign_from_multiple_old_puzzles(self, mock_log):
        """Solver on multiple puzzles (stale data) should be unassigned from all."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor

        fetchone_count = {"n": 0}

        # fetchall returns two old puzzles
        cursor.fetchall.return_value = [{"id": 284}, {"id": 285}]

        def mock_fetchone():
            fetchone_count["n"] += 1
            n = fetchone_count["n"]
            # unassign calls for 284 and 285, then assign calls for 287
            if n <= 2:
                return {"current_solvers": json.dumps({"solvers": [{"solver_id": 101}]})}
            elif n == 3:
                return {"current_solvers": json.dumps({"solvers": []})}
            elif n == 4:
                return {"solver_history": json.dumps({"solvers": []})}
            return None

        cursor.fetchone = mock_fetchone

        assign_solver_to_puzzle(287, 101, conn)

        # Verify unassign was called for both old puzzles
        unassign_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c)
        ]
        # Should have: unassign 284, unassign 285, assign 287 = at least 3 UPDATE calls
        assert len(unassign_calls) >= 3, f"Expected at least 3 current_solvers UPDATEs, got {len(unassign_calls)}"


class TestAssignSolverHistoryType:
    """Test that solver_history also uses consistent int types."""

    @patch('pblib.debug_log')
    def test_history_stores_int_from_string(self, mock_log):
        """String solver_id should be stored as int in solver_history."""
        conn, cursor = _make_mock_conn()

        assign_solver_to_puzzle("287", "101", conn)

        update_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET solver_history' in str(c)
        ]
        assert len(update_calls) >= 1
        stored_json = update_calls[0][0][1][0]
        stored = json.loads(stored_json)
        assert stored["solvers"][0]["solver_id"] == 101
        assert isinstance(stored["solvers"][0]["solver_id"], int)

    @patch('pblib.debug_log')
    def test_history_no_duplicate_string_vs_int(self, mock_log):
        """String "101" should not duplicate existing int 101 in history."""
        existing_history = json.dumps({"solvers": [{"solver_id": 101}]})
        conn, cursor = _make_mock_conn(solver_history_json=existing_history)

        assign_solver_to_puzzle("287", "101", conn)

        update_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET solver_history' in str(c)
        ]
        assert len(update_calls) == 0, "Should not duplicate solver in history"
