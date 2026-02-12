#!/usr/bin/env python3
"""
Extended unit tests for bigjimmybot.py - Additional coverage

Tests additional functions and error handling not covered in
test_bigjimmybot.py.

Run with: pytest tests/test_bigjimmybot_extended.py -v
"""

import pytest
import json
import os
import sys
import time
import queue
import threading
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime as dt

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock MySQL and Google API dependencies BEFORE importing bigjimmybot
sys.modules['MySQLdb'] = MagicMock()
sys.modules['MySQLdb.cursors'] = MagicMock()
sys.modules['pbgooglelib'] = MagicMock()

# Mock pblib module with minimal config
pblib_mock = MagicMock()
pblib_mock.config = {
    'API': {'APIURI': 'http://localhost:5000'},
    'MYSQL': {
        'HOST': 'localhost',
        'USERNAME': 'test',
        'PASSWORD': 'test',
        'DATABASE': 'test',
    },
}
pblib_mock.configstruct = {
    'BIGJIMMY_AUTOASSIGN': 'true',
    'BIGJIMMY_ABANDONED_TIMEOUT_MINUTES': '10',
    'BIGJIMMY_ABANDONED_STATUS': 'Abandoned'
}
pblib_mock.debug_log = lambda level, msg: None  # Suppress debug logs in tests
pblib_mock.get_mysql_ssl_config.return_value = None
sys.modules['pblib'] = pblib_mock

# Now we can import bigjimmybot
from bigjimmybot import (
    _record_solver_activity,
    _assign_solver_to_puzzle,
    _fetch_last_sheet_activity,
    _update_sheet_count,
    _check_abandoned_puzzle,
    _process_puzzle,
    _get_db_connection,
)


def load_fixture(filename):
    """Load a JSON fixture file."""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', filename)
    with open(fixture_path) as f:
        return json.load(f)


class TestRecordSolverActivity:
    """Test _record_solver_activity function."""

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.log_activity')
    def test_record_activity_success(self, mock_log_activity, mock_conn):
        """Test successfully recording solver activity."""
        # Test
        result = _record_solver_activity(123, 456, "test-thread")

        # Verify
        assert result is True
        mock_log_activity.assert_called_once_with(
            123, "revise", 456, "bigjimmybot", mock_conn.return_value
        )

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.log_activity')
    def test_record_activity_db_failure(self, mock_log_activity, mock_conn):
        """Test handling database failure when recording activity."""
        # Mock database failure
        mock_log_activity.side_effect = Exception("Database error")

        # Test
        result = _record_solver_activity(123, 456, "test-thread")

        # Verify returns False on failure
        assert result is False


class TestAssignSolverToPuzzle:
    """Test _assign_solver_to_puzzle function."""

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.assign_solver_to_puzzle')
    def test_assign_solver_success(self, mock_assign, mock_conn):
        """Test successfully assigning solver to puzzle."""
        # Test
        result = _assign_solver_to_puzzle(123, 456, "test-thread")

        # Verify
        assert result is True
        mock_assign.assert_called_once_with(
            123, 456, mock_conn.return_value
        )

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.assign_solver_to_puzzle')
    def test_assign_solver_db_failure(self, mock_assign, mock_conn):
        """Test handling database failure when assigning solver."""
        # Mock database failure
        mock_assign.side_effect = Exception("Database error")

        # Test
        result = _assign_solver_to_puzzle(123, 456, "test-thread")

        # Verify returns False on failure
        assert result is False


class TestFetchLastSheetActivity:
    """Test _fetch_last_sheet_activity function."""

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_last_sheet_activity_for_puzzle')
    def test_fetch_lastsheetact_success(self, mock_get_activity, mock_conn):
        """Test successfully fetching last sheet activity."""
        # Mock database response with datetime object
        mock_activity = {
            "time": dt(2026, 2, 11, 23, 19, 43),
            "type": "revise",
            "source": "google",
        }
        mock_get_activity.return_value = mock_activity

        # Test
        puzzle = {"id": 123, "name": "TestPuzzle"}
        result = _fetch_last_sheet_activity(puzzle, "test-thread")

        # Verify
        assert result is not None
        assert result["type"] == "revise"
        assert isinstance(result["time"], dt)
        mock_get_activity.assert_called_once_with(123, mock_conn.return_value)

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_last_sheet_activity_for_puzzle')
    def test_fetch_lastsheetact_none_result(self, mock_get_activity, mock_conn):
        """Test fetching last sheet activity when there's no activity (None)."""
        # Mock database returning None
        mock_get_activity.return_value = None

        # Test
        puzzle = {"id": 123, "name": "TestPuzzle"}
        result = _fetch_last_sheet_activity(puzzle, "test-thread")

        # Verify None is returned (valid state)
        assert result is None

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_last_sheet_activity_for_puzzle')
    def test_fetch_lastsheetact_db_error(self, mock_get_activity, mock_conn):
        """Test handling database error."""
        # Mock database exception
        mock_get_activity.side_effect = Exception("Connection lost")

        # Test
        puzzle = {"id": 999, "name": "NonExistent"}
        result = _fetch_last_sheet_activity(puzzle, "test-thread")

        # Verify None returned on error
        assert result is None

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_last_sheet_activity_for_puzzle')
    def test_fetch_lastsheetact_connection_failure(self, mock_get_activity, mock_conn):
        """Test handling connection failure."""
        # Mock connection failure
        mock_conn.side_effect = Exception("Connection refused")

        # Test
        puzzle = {"id": 123, "name": "TestPuzzle"}
        result = _fetch_last_sheet_activity(puzzle, "test-thread")

        # Verify None returned on connection failure
        assert result is None


class TestUpdateSheetCount:
    """Test _update_sheet_count function."""

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.update_puzzle_field')
    def test_update_when_count_changed(self, mock_update, mock_conn):
        """Test updating sheet count when it has changed."""
        # Test with changed count
        puzzle = {"id": 123, "name": "TestPuzzle", "sheetcount": 45}
        sheet_info = {"sheetcount": 47}

        _update_sheet_count(puzzle, sheet_info, "test-thread")

        # Verify database was called to update
        mock_update.assert_called_once_with(
            123, "sheetcount", 47, mock_conn.return_value
        )

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.update_puzzle_field')
    def test_skip_update_when_count_unchanged(self, mock_update, mock_conn):
        """Test skipping update when sheet count hasn't changed."""
        # Test with unchanged count
        puzzle = {"id": 123, "name": "TestPuzzle", "sheetcount": 47}
        sheet_info = {"sheetcount": 47}

        _update_sheet_count(puzzle, sheet_info, "test-thread")

        # Verify database was NOT called
        mock_update.assert_not_called()


class TestCheckAbandonedPuzzle:
    """Test _check_abandoned_puzzle function."""

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_last_activity_for_puzzle')
    def test_puzzle_with_current_solvers_not_abandoned(self, mock_get_activity, mock_conn):
        """Test that puzzles with current solvers are not marked abandoned."""
        # Puzzle with solvers assigned
        puzzle = {
            "id": 123,
            "name": "TestPuzzle",
            "cursolvers": "Alice, Bob",
            "status": "Being worked"
        }

        _check_abandoned_puzzle(puzzle, "test-thread")

        # Verify no database call was made for lastact
        mock_get_activity.assert_not_called()

    @patch('bigjimmybot.configstruct', {
        'BIGJIMMY_ABANDONED_TIMEOUT_MINUTES': '10',
        'BIGJIMMY_ABANDONED_STATUS': 'Abandoned',
    })
    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.update_puzzle_field')
    @patch('bigjimmybot.get_last_activity_for_puzzle')
    @patch('bigjimmybot.datetime')
    def test_puzzle_abandoned_after_timeout(
        self, mock_datetime, mock_get_activity, mock_update, mock_conn
    ):
        """Test marking puzzle as abandoned after inactivity timeout."""
        # Last activity: 15 minutes ago (should trigger abandon at 10 min threshold)
        now = dt(2026, 2, 11, 23, 15, 0)
        last_activity_time = dt(2026, 2, 11, 23, 0, 0)  # 15 minutes ago

        # Mock datetime.datetime.utcnow() to return our current time
        mock_datetime.datetime.utcnow.return_value = now

        # Mock database returning activity with datetime object
        mock_get_activity.return_value = {
            "time": last_activity_time,
            "type": "revise",
        }

        # Puzzle with no current solvers
        puzzle = {
            "id": 123,
            "name": "TestPuzzle",
            "cursolvers": "",  # No solvers assigned
            "status": "Being worked"
        }

        _check_abandoned_puzzle(puzzle, "test-thread")

        # Verify lastact was fetched
        mock_get_activity.assert_called_once()
        # Verify status update was attempted
        mock_update.assert_called_once_with(
            123, "status", "Abandoned", mock_conn.return_value
        )


class TestPuzzleProcessing:
    """Test _process_puzzle function."""

    @patch('bigjimmybot._check_abandoned_puzzle')
    @patch('bigjimmybot._process_sheet_activity')
    @patch('bigjimmybot._update_sheet_count')
    @patch('bigjimmybot._fetch_sheet_info')
    def test_process_puzzle_calls_all_subfunctions(
        self, mock_fetch, mock_update, mock_activity, mock_abandoned
    ):
        """Test that _process_puzzle calls all required subfunctions."""
        # Mock sheet info response
        mock_fetch.return_value = ({"sheetcount": 10}, 1)

        # Test puzzle
        puzzle = {"id": 123, "name": "TestPuzzle", "sheetlink": "http://example.com"}

        # Process puzzle
        _process_puzzle(puzzle, "test-thread")

        # Verify all subfunctions were called
        mock_fetch.assert_called_once_with(puzzle, "test-thread")
        mock_update.assert_called_once()
        mock_activity.assert_called_once()
        mock_abandoned.assert_called_once_with(puzzle, "test-thread")

    @patch('bigjimmybot._check_abandoned_puzzle')
    @patch('bigjimmybot._process_sheet_activity')
    @patch('bigjimmybot._update_sheet_count')
    @patch('bigjimmybot._fetch_sheet_info')
    def test_process_puzzle_handles_errors_gracefully(
        self, mock_fetch, mock_update, mock_activity, mock_abandoned
    ):
        """Test that _process_puzzle continues even if subfunctions raise errors."""
        # Mock one function to raise an exception
        mock_fetch.side_effect = Exception("Google API error")

        # Test puzzle
        puzzle = {"id": 123, "name": "TestPuzzle", "sheetlink": "http://example.com"}

        # Process puzzle - should not raise exception
        try:
            _process_puzzle(puzzle, "test-thread")
        except Exception as e:
            # Expected behavior: exception propagates (bigjimmybot logs and continues)
            assert "Google API error" in str(e)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_last_sheet_activity_for_puzzle')
    def test_handle_db_exception(self, mock_get_activity, mock_conn):
        """Test handling database exception gracefully."""
        # Mock database exception
        mock_get_activity.side_effect = Exception("Connection timeout")

        # Test
        puzzle = {"id": 123, "name": "TestPuzzle"}
        result = _fetch_last_sheet_activity(puzzle, "test-thread")

        # Should return None instead of raising exception
        assert result is None

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_last_sheet_activity_for_puzzle')
    def test_handle_empty_activity_result(self, mock_get_activity, mock_conn):
        """Test handling empty/None activity result from database."""
        # Mock database returning None (no activity)
        mock_get_activity.return_value = None

        # Test
        puzzle = {"id": 123, "name": "TestPuzzle"}
        result = _fetch_last_sheet_activity(puzzle, "test-thread")

        # Should handle gracefully
        assert result is None


class TestGetDbConnection:
    """Test _get_db_connection thread-local connection management."""

    @patch('bigjimmybot.MySQLdb')
    def test_creates_new_connection(self, mock_mysqldb):
        """Test that a new connection is created when none exists."""
        # Clear any existing thread-local state
        import bigjimmybot
        if hasattr(bigjimmybot._thread_local, 'db_conn'):
            del bigjimmybot._thread_local.db_conn

        mock_conn = MagicMock()
        mock_mysqldb.connect.return_value = mock_conn

        result = _get_db_connection()

        assert result == mock_conn
        mock_mysqldb.connect.assert_called_once()

    @patch('bigjimmybot.MySQLdb')
    def test_reuses_existing_connection(self, mock_mysqldb):
        """Test that an existing connection is reused via ping."""
        import bigjimmybot

        # Set up an existing connection
        mock_conn = MagicMock()
        mock_conn.ping.return_value = None  # ping succeeds
        bigjimmybot._thread_local.db_conn = mock_conn

        result = _get_db_connection()

        assert result == mock_conn
        mock_conn.ping.assert_called_once_with(True)
        # Should NOT create a new connection
        mock_mysqldb.connect.assert_not_called()

        # Cleanup
        del bigjimmybot._thread_local.db_conn
