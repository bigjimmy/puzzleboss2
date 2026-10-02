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


def _make_mock_conn(current_solvers_json=None, solver_history_json=None,
                    puzzle_status="Being worked", old_puzzles=()):
    """Create a mock DB connection that simulates puzzle JSON columns.

    The mock cursor returns appropriate values for the SELECT queries
    in assign/unassign functions, and tracks UPDATE calls.

    Args:
        puzzle_status: The puzzle's current status (default "Being worked").
            Used by assign_solver_to_puzzle to decide whether to transition
            "New"/"Abandoned" → "Being worked".
        old_puzzles: ids of other puzzles solver 101 is currently on.
    """
    if current_solvers_json is None:
        current_solvers_json = json.dumps({"solvers": []})
    if solver_history_json is None:
        solver_history_json = json.dumps({"solvers": []})

    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor

    # Dispatch fetchone/fetchall on the *last executed SQL* rather than a call
    # ordinal. The assign/unassign paths issue a variable number of queries
    # (status transitions re-enter log_activity, and log_activity does a
    # lastact write-through re-query when Redis is enabled), so a positional
    # counter is too brittle. We key on distinctive fragments of each SELECT.
    # cursor.execute stays the MagicMock (tests inspect its call_args_list);
    # we just read the most recent call to route the fetch.
    def _last_call():
        if not cursor.execute.call_args_list:
            return "", ()
        args = cursor.execute.call_args_list[-1][0]
        return str(args[0]), (args[1] if len(args) > 1 else ())

    def _puzzle_row(pid):
        if pid in old_puzzles:
            return {"id": pid, "status": "Being worked", "solver_history": None,
                    "current_solvers": json.dumps({"solvers": [{"solver_id": 101}]})}
        return {"id": pid, "status": puzzle_status, "solver_history": solver_history_json,
                "current_solvers": current_solvers_json}

    def mock_fetchone():
        sql, _ = _last_call()
        if "FROM solver" in sql:
            return {"id": 101}  # solver exists
        if "current_solvers" in sql:
            return {"current_solvers": current_solvers_json}  # unassign
        if "FROM activity" in sql or "from activity" in sql:
            # lastact write-through re-query (only runs when Redis enabled)
            return {"id": 1, "puzzle_id": 287, "solver_id": 101,
                    "source": "puzzleboss", "type": "assignment", "time": None}
        return None

    def mock_fetchall():
        sql, params = _last_call()
        if "JSON_TABLE" in sql:
            return [{"id": pid} for pid in old_puzzles]
        if "FOR UPDATE" in sql and "FROM puzzle" in sql:
            return [_puzzle_row(pid) for pid in params]
        return []

    cursor.fetchone = mock_fetchone
    cursor.fetchall = mock_fetchall

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
        """Assigning solver should remove it from its old puzzle."""
        conn, cursor = _make_mock_conn(old_puzzles=(284,))

        assign_solver_to_puzzle(287, 101, conn)

        unassign_calls = [
            c for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c) and c[0][1][1] == 284
        ]
        assert len(unassign_calls) == 1, "Should unassign from old puzzle 284"
        stored = json.loads(unassign_calls[0][0][1][0])
        assert len(stored["solvers"]) == 0, "Old puzzle should have no solvers"

    @patch('pblib.debug_log')
    def test_unassign_from_multiple_old_puzzles(self, mock_log):
        """Solver on multiple puzzles (stale data) should be unassigned from all."""
        conn, cursor = _make_mock_conn(old_puzzles=(284, 285))

        assign_solver_to_puzzle(287, 101, conn)

        updated = [
            c[0][1][1] for c in cursor.execute.call_args_list
            if 'SET current_solvers' in str(c)
        ]
        assert sorted(updated) == [284, 285, 287]


class TestAssignLocking:
    """Assignment is one locked transaction (audit finding H7).

    current_solvers/solver_history are JSON read-modify-writes; without row
    locks two concurrent assignments can overwrite each other.
    """

    @patch('pblib.debug_log')
    def test_locks_solver_then_puzzles_in_id_order(self, mock_log):
        conn, cursor = _make_mock_conn(old_puzzles=(300, 284))

        assign_solver_to_puzzle(287, 101, conn)

        sqls = [str(c[0][0]) for c in cursor.execute.call_args_list]
        locks = [i for i, q in enumerate(sqls) if "FOR UPDATE" in q]
        assert len(locks) == 2
        assert "FROM solver" in sqls[locks[0]]
        assert "FROM puzzle" in sqls[locks[1]] and "ORDER BY id" in sqls[locks[1]]
        assert cursor.execute.call_args_list[locks[1]][0][1] == (284, 287, 300)
        # every read-modify-write happens after both locks
        first_update = min(i for i, q in enumerate(sqls) if q.startswith("UPDATE puzzle"))
        assert first_update > locks[1]

    @patch('pblib.debug_log')
    def test_commits_before_locking(self, mock_log):
        """A fresh transaction, so the solver search reads after the lock."""
        conn, cursor = _make_mock_conn()
        events = []
        conn.commit.side_effect = lambda: events.append("commit")
        cursor.execute.side_effect = lambda sql, *a: events.append(sql)

        assign_solver_to_puzzle(287, 101, conn)

        first_lock = next(i for i, e in enumerate(events) if "FOR UPDATE" in e)
        assert "commit" in events[:first_lock]

    @patch('pblib.debug_log')
    def test_rejected_assignment_leaves_old_puzzle_alone(self, mock_log):
        conn, cursor = _make_mock_conn(puzzle_status="Solved", old_puzzles=(284,))

        with pytest.raises(ValueError, match="already solved"):
            assign_solver_to_puzzle(287, 101, conn)

        assert not any(
            'SET current_solvers' in str(c) for c in cursor.execute.call_args_list
        )
        conn.rollback.assert_called()

    @patch('pblib.debug_log')
    def test_unassign_locks_row(self, mock_log):
        conn, cursor = _make_mock_conn(
            current_solvers_json=json.dumps({"solvers": [{"solver_id": 101}]})
        )
        unassign_solver_from_puzzle(287, 101, conn)
        first = str(cursor.execute.call_args_list[0][0][0])
        assert "FOR UPDATE" in first


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
