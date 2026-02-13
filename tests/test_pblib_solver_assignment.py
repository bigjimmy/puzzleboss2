#!/usr/bin/env python3
"""
Unit tests for pblib solver assignment functions.

Tests verify that solver_id is always stored as INT in JSON, matching the
solver.id column type (INT(11)).  All SQL functions use JSON_TABLE with
INT PATH to extract solver_ids, which handles both int and string values.
Assumes the normalize_solver_ids migration has been run so all existing
database entries use integer solver_ids.

Run with: pytest tests/test_pblib_solver_assignment.py -v
"""

import json
import os
import sys
import pytest
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


def _make_mock_conn(current_solvers_json=None, solver_history_json=None, puzzle_status="Being worked"):
    """Create a mock DB connection that simulates puzzle JSON columns.

    The mock cursor returns appropriate values for the SELECT queries
    in assign/unassign functions, and tracks UPDATE calls.

    Args:
        puzzle_status: The puzzle's current status (default "Being worked").
            Used by assign_solver_to_puzzle to decide whether to transition
            "New"/"Abandoned" → "Being worked".
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
    # 1. solver_exists() → SELECT id FROM solver → fetchone (returns solver row)
    # 2. JSON_TABLE lookup for current puzzle → fetchall (returns [] = not assigned)
    # 3. SELECT current_solvers, status → fetchone
    # 4. SELECT solver_history → fetchone
    # 5. log_activity() → INSERT INTO activity (uses execute, no fetchone)
    cursor.fetchall.return_value = []  # Not currently assigned to any puzzle

    def mock_fetchone():
        fetchone_count["n"] += 1
        n = fetchone_count["n"]
        if n == 1:
            return {"id": 101}  # solver_exists check
        elif n == 2:
            return {"current_solvers": current_solvers_json, "status": puzzle_status}
        elif n == 3:
            return {"solver_history": solver_history_json}
        return None

    cursor.fetchone = mock_fetchone

    return conn, cursor


class TestAssignSolverTypeNormalization:
    """Test that solver_id is always stored as INT in JSON.

    Storing as int matches the native solver.id column type (INT(11)).
    All SQL functions use JSON_TABLE with INT PATH to extract solver_ids,
    which handles both int and string JSON values via coercion.

    Assumes the normalize_solver_ids migration has been run so all existing
    data in the database uses integer solver_ids.
    """

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
        assert stored["solvers"][0]["solver_id"] == 101
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
    def test_no_duplicate_when_already_present(self, mock_log):
        """Assigning solver already in current_solvers should not duplicate."""
        existing = json.dumps({"solvers": [{"solver_id": 101}]})
        conn, cursor = _make_mock_conn(current_solvers_json=existing)

        assign_solver_to_puzzle(287, 101, conn)

        update_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c)
        ]
        assert len(update_calls) == 0, "Should not duplicate solver in current_solvers"


class TestUnassignSolverTypeNormalization:
    """Test that unassign handles int/string solver_id input correctly.

    Post-migration: all database entries use integer solver_ids.
    Both int and string caller input must be normalized to int to match.
    """

    @patch('pblib.debug_log')
    def test_string_id_removes_int_entry(self, mock_log):
        """String solver_id "101" from Flask should remove int entry 101."""
        existing = json.dumps({"solvers": [{"solver_id": 101}]})
        conn, cursor = _make_mock_conn(current_solvers_json=existing)

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
    def test_int_id_removes_int_entry(self, mock_log):
        """Int solver_id 101 from bigjimmybot should remove int entry 101."""
        existing = json.dumps({"solvers": [{"solver_id": 101}]})
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
        assert len(stored["solvers"]) == 0, "Solver should have been removed"

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
    def test_unassign_from_old_puzzle(self, mock_log):
        """Assigning solver should unassign from old puzzle first."""
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
            # 1. solver_exists() → SELECT id FROM solver
            # 2. unassign_solver_from_puzzle: SELECT current_solvers for puzzle 284
            # 3. assign: SELECT current_solvers, status for puzzle 287
            # 4. assign: SELECT solver_history for puzzle 287
            if n == 1:
                return {"id": 101}  # solver_exists
            elif n == 2:
                return {"current_solvers": json.dumps({"solvers": [{"solver_id": 101}]})}
            elif n == 3:
                return {"current_solvers": json.dumps({"solvers": []}), "status": "Being worked"}
            elif n == 4:
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
            # 1. solver_exists() → SELECT id FROM solver
            # 2-3. unassign calls for 284 and 285 (SELECT current_solvers)
            # 4. assign: SELECT current_solvers, status for 287
            # 5. assign: SELECT solver_history for 287
            if n == 1:
                return {"id": 101}  # solver_exists
            elif n <= 3:
                return {"current_solvers": json.dumps({"solvers": [{"solver_id": 101}]})}
            elif n == 4:
                return {"current_solvers": json.dumps({"solvers": []}), "status": "Being worked"}
            elif n == 5:
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
    """Test that solver_history also stores solver_id as int."""

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
    def test_history_no_duplicate_when_already_present(self, mock_log):
        """Solver already in history should not be added again."""
        existing_history = json.dumps({"solvers": [{"solver_id": 101}]})
        conn, cursor = _make_mock_conn(solver_history_json=existing_history)

        assign_solver_to_puzzle("287", "101", conn)

        update_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET solver_history' in str(c)
        ]
        assert len(update_calls) == 0, "Should not write to history when solver already present"


class TestAssignStatusTransition:
    """Test that assign_solver_to_puzzle transitions puzzle status.

    When a solver is assigned, puzzles in "New" or "Abandoned" status
    should automatically transition to "Being worked". This ensures
    the invariant holds regardless of whether the assignment comes from
    the web UI (via pbrest.py) or bigjimmybot's auto-assign.
    """

    @patch('pblib.debug_log')
    def test_new_puzzle_transitions_to_being_worked(self, mock_log):
        """Puzzle with status 'New' should become 'Being worked' on assignment."""
        conn, cursor = _make_mock_conn(puzzle_status="New")

        assign_solver_to_puzzle(287, 101, conn)

        status_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET status' in str(c)
        ]
        assert len(status_calls) == 1, "Expected one status UPDATE"
        assert status_calls[0][0][1] == ("Being worked", 287)

    @patch('pblib.debug_log')
    def test_abandoned_puzzle_transitions_to_being_worked(self, mock_log):
        """Puzzle with status 'Abandoned' should become 'Being worked' on assignment."""
        conn, cursor = _make_mock_conn(puzzle_status="Abandoned")

        assign_solver_to_puzzle(287, 101, conn)

        status_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET status' in str(c)
        ]
        assert len(status_calls) == 1, "Expected one status UPDATE"
        assert status_calls[0][0][1] == ("Being worked", 287)

    @patch('pblib.debug_log')
    def test_being_worked_puzzle_no_status_change(self, mock_log):
        """Puzzle already 'Being worked' should not get a redundant status UPDATE."""
        conn, cursor = _make_mock_conn(puzzle_status="Being worked")

        assign_solver_to_puzzle(287, 101, conn)

        status_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET status' in str(c)
        ]
        assert len(status_calls) == 0, "Should not update status when already 'Being worked'"

    @patch('pblib.debug_log')
    def test_solved_puzzle_raises_error(self, mock_log):
        """Puzzle with status 'Solved' should raise ValueError (cannot assign)."""
        conn, cursor = _make_mock_conn(puzzle_status="Solved")

        with pytest.raises(ValueError, match="already solved"):
            assign_solver_to_puzzle(287, 101, conn)
