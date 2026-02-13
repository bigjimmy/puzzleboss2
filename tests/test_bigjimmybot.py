#!/usr/bin/env python3
"""
Unit tests for bigjimmybot.py

These tests use mocking to test business logic without requiring:
- Running Flask API server
- Running MySQL database
- Google API access

Run with: pytest tests/test_bigjimmybot.py -v
"""

import pytest
import json
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock MySQL and Google API dependencies BEFORE importing bigjimmybot
sys.modules['MySQLdb'] = MagicMock()
sys.modules['MySQLdb.cursors'] = MagicMock()
sys.modules['pbgooglelib'] = MagicMock()

# Mock pblib module with minimal config
pblib_mock = MagicMock()
pblib_mock.config = {
    'MYSQL': {
        'HOST': 'localhost',
        'USERNAME': 'test',
        'PASSWORD': 'test',
        'DATABASE': 'test',
    },
}
pblib_mock.configstruct = {'BIGJIMMY_AUTOASSIGN': 'true'}
pblib_mock.debug_log = lambda level, msg: None  # Suppress debug logs in tests
pblib_mock.create_db_connection.return_value = MagicMock()
sys.modules['pblib'] = pblib_mock

# Now we can import bigjimmybot
from bigjimmybot import (
    _parse_revision_timestamp,
    _get_solver_id,
    _process_activity_records,
)


def load_fixture(filename):
    """Load a JSON fixture file."""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', filename)
    with open(fixture_path) as f:
        return json.load(f)


def _make_solver_with_lastact(fixture_name, lastact_time=None):
    """Build a solver dict from fixture, adding lastact with a datetime object.

    Args:
        fixture_name: JSON fixture filename (solver dict without API envelope)
        lastact_time: datetime object for lastact, or None for no activity
    """
    solver = load_fixture(fixture_name)
    if lastact_time is not None:
        solver["lastact"] = {
            "time": lastact_time,
            "type": "revise",
            "source": "bigjimmybot",
            "solver_id": solver["id"],
            "puzzle_id": 123,
        }
    else:
        solver["lastact"] = None
    return solver


class TestTimestampParsing:
    """Test timestamp parsing functions."""

    def test_parse_revision_timestamp_valid(self):
        """Test parsing valid Google Drive revision timestamp."""
        timestamp = "2026-02-12T01:40:46.123Z"
        result = _parse_revision_timestamp(timestamp)
        # Verify it returns a numeric timestamp with milliseconds
        assert isinstance(result, float)
        assert result > 0
        # Verify milliseconds are preserved
        assert result != int(result)  # Has fractional part
        # Verify it's reasonable (year 2026)
        assert 1700000000 < result < 1800000000


class TestSolverLookup:
    """Test solver lookup with mocked database."""

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_solver_by_name_from_db')
    def test_get_solver_id_by_name_found(self, mock_get_solver, mock_conn):
        """Test successful solver lookup by name."""
        # Mock database response (solver dict directly, no API envelope)
        solver_data = load_fixture('solver_benoc.json')
        mock_get_solver.return_value = solver_data

        # Test
        result = _get_solver_id("benoc", "name")

        # Verify
        assert result == 456
        mock_get_solver.assert_called_once()
        # Verify username was lowercased
        assert mock_get_solver.call_args[0][0] == "benoc"

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_solver_by_name_from_db')
    def test_get_solver_id_by_email_found(self, mock_get_solver, mock_conn):
        """Test successful solver lookup by email (extracts username)."""
        # Mock database response
        solver_data = load_fixture('solver_benoc.json')
        mock_get_solver.return_value = solver_data

        # Test with full email
        result = _get_solver_id("benoc@example.com", "email")

        # Verify - should extract "benoc" from email
        assert result == 456
        assert mock_get_solver.call_args[0][0] == "benoc"

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_solver_by_name_from_db')
    def test_get_solver_id_not_found(self, mock_get_solver, mock_conn):
        """Test solver lookup when solver doesn't exist."""
        # Mock database returning None (not found)
        mock_get_solver.return_value = None

        # Test
        result = _get_solver_id("nonexistent", "name")

        # Verify returns 0 for not found
        assert result == 0

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_solver_by_name_from_db')
    def test_get_solver_id_db_error(self, mock_get_solver, mock_conn):
        """Test solver lookup when database raises exception."""
        # Mock database exception
        mock_get_solver.side_effect = Exception("Database connection lost")

        # Test
        result = _get_solver_id("benoc", "name")

        # Verify returns 0 for error
        assert result == 0

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_solver_by_name_from_db')
    def test_get_solver_id_connection_failure(self, mock_get_solver, mock_conn):
        """Test solver lookup when DB connection fails."""
        # Mock connection failure
        mock_conn.side_effect = Exception("Connection refused")

        # Test
        result = _get_solver_id("benoc", "name")

        # Verify returns 0 for connection error
        assert result == 0

    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_solver_by_name_from_db')
    def test_get_solver_id_case_insensitive(self, mock_get_solver, mock_conn):
        """Test solver lookup is case-insensitive."""
        # Mock database response
        solver_data = load_fixture('solver_benoc.json')
        mock_get_solver.return_value = solver_data

        # Test with different cases
        result1 = _get_solver_id("BENOC", "name")
        result2 = _get_solver_id("BeNoC", "name")

        # Verify both work
        assert result1 == 456
        assert result2 == 456
        # Verify both were lowercased in DB call
        assert mock_get_solver.call_args_list[0][0][0] == "benoc"
        assert mock_get_solver.call_args_list[1][0][0] == "benoc"


class TestActivityProcessing:
    """Test activity record processing logic."""

    @patch('bigjimmybot.configstruct', {'BIGJIMMY_AUTOASSIGN': 'true'})
    @patch('bigjimmybot._assign_solver_to_puzzle')
    @patch('bigjimmybot._record_solver_activity')
    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_solver_by_id_from_db')
    @patch('bigjimmybot._get_solver_id')
    def test_process_activity_assigns_new_solver(
        self, mock_get_solver, mock_get_solver_by_id, mock_conn, mock_record, mock_assign
    ):
        """Test that new activity triggers solver assignment."""
        # Setup mocks
        mock_get_solver.return_value = 456  # benoc's ID

        # Mock solver info from DB - on different puzzle, with old lastact
        solver_info = _make_solver_with_lastact(
            'solver_benoc.json',
            lastact_time=datetime(2026, 2, 11, 23, 19, 43),
        )
        mock_get_solver_by_id.return_value = solver_info

        # Test data - edit timestamp is VERY NEW (way newer than solver's last activity)
        puzzle = load_fixture('puzzle_data.json')
        records = [
            {"solvername": "benoc", "timestamp": 1900000000}  # Future timestamp (year ~2030)
        ]
        last_sheet_act_ts = 0  # No previous activity

        # Test
        _process_activity_records(records, puzzle, last_sheet_act_ts, "test-thread", True)

        # Verify activity was recorded with the actual edit timestamp
        mock_record.assert_called_once_with(123, 456, "test-thread", edit_ts=1900000000)

        # Verify solver was assigned
        mock_assign.assert_called_once_with(123, 456, "test-thread")

    @patch('bigjimmybot.configstruct', {'BIGJIMMY_AUTOASSIGN': 'true'})
    @patch('bigjimmybot._assign_solver_to_puzzle')
    @patch('bigjimmybot._record_solver_activity')
    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_solver_by_id_from_db')
    @patch('bigjimmybot._get_solver_id')
    def test_process_activity_records_after_assign(
        self, mock_get_solver, mock_get_solver_by_id, mock_conn, mock_record, mock_assign
    ):
        """Test that activity is recorded AFTER assignment decision (not before).

        This is critical: if _record_solver_activity() runs before
        _assign_solver_to_puzzle(), the freshly-inserted activity row
        pollutes the solver's lastact, making edit_ts <= last_solver_act_ts
        always true and preventing assignment.
        """
        # Track call order
        call_order = []
        mock_assign.side_effect = lambda *a, **kw: call_order.append('assign')
        mock_record.side_effect = lambda *a, **kw: call_order.append('record')

        mock_get_solver.return_value = 456
        solver_info = _make_solver_with_lastact(
            'solver_benoc.json',
            lastact_time=datetime(2026, 2, 11, 23, 19, 43),
        )
        mock_get_solver_by_id.return_value = solver_info

        puzzle = load_fixture('puzzle_data.json')
        records = [
            {"solvername": "benoc", "timestamp": 1900000000}
        ]

        _process_activity_records(records, puzzle, 0, "test-thread", True)

        # Verify assignment happens BEFORE activity recording
        assert call_order == ['assign', 'record']

    @patch('bigjimmybot.configstruct', {'BIGJIMMY_AUTOASSIGN': 'true'})
    @patch('bigjimmybot._assign_solver_to_puzzle')
    @patch('bigjimmybot._record_solver_activity')
    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_solver_by_id_from_db')
    @patch('bigjimmybot._get_solver_id')
    def test_process_activity_skips_already_assigned(
        self, mock_get_solver, mock_get_solver_by_id, mock_conn, mock_record, mock_assign
    ):
        """Test that already-assigned solver is skipped for assignment."""
        # Setup mocks
        mock_get_solver.return_value = 456

        # Mock solver already on this puzzle
        solver_info = _make_solver_with_lastact(
            'solver_already_assigned.json',
            lastact_time=datetime(2026, 2, 11, 23, 19, 43),
        )
        mock_get_solver_by_id.return_value = solver_info

        # Test data
        puzzle = {"id": 123, "name": "TestPuzzle"}
        records = [
            {"solvername": "benoc", "timestamp": 1770860446}
        ]
        last_sheet_act_ts = 0

        # Test
        _process_activity_records(records, puzzle, last_sheet_act_ts, "test-thread", True)

        # Verify activity was recorded
        mock_record.assert_called_once()

        # Verify solver was NOT assigned (already on this puzzle)
        mock_assign.assert_not_called()

    @patch('bigjimmybot.configstruct', {'BIGJIMMY_AUTOASSIGN': 'false'})
    @patch('bigjimmybot._assign_solver_to_puzzle')
    @patch('bigjimmybot._record_solver_activity')
    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_solver_by_id_from_db')
    @patch('bigjimmybot._get_solver_id')
    def test_process_activity_respects_autoassign_disabled(
        self, mock_get_solver, mock_get_solver_by_id, mock_conn, mock_record, mock_assign
    ):
        """Test that auto-assign is skipped when disabled."""
        # Setup mocks
        mock_get_solver.return_value = 456

        # Mock solver info
        solver_info = _make_solver_with_lastact(
            'solver_benoc.json',
            lastact_time=datetime(2026, 2, 11, 23, 19, 43),
        )
        mock_get_solver_by_id.return_value = solver_info

        # Test data
        puzzle = load_fixture('puzzle_data.json')
        records = [
            {"solvername": "benoc", "timestamp": 1770860446}
        ]
        last_sheet_act_ts = 0

        # Test with BIGJIMMY_AUTOASSIGN = false
        _process_activity_records(records, puzzle, last_sheet_act_ts, "test-thread", True)

        # Verify activity was recorded
        mock_record.assert_called_once()

        # Verify solver was NOT assigned (feature disabled)
        mock_assign.assert_not_called()

    @patch('bigjimmybot.configstruct', {'BIGJIMMY_AUTOASSIGN': 'true'})
    @patch('bigjimmybot._assign_solver_to_puzzle')
    @patch('bigjimmybot._record_solver_activity')
    @patch('bigjimmybot._get_db_connection')
    @patch('bigjimmybot.get_solver_by_id_from_db')
    @patch('bigjimmybot._get_solver_id')
    def test_process_activity_skips_old_edit(
        self, mock_get_solver, mock_get_solver_by_id, mock_conn, mock_record, mock_assign
    ):
        """Test that edit older than solver's last activity is skipped."""
        # Setup mocks
        mock_get_solver.return_value = 456

        # Mock solver with recent activity (lastact time is NEWER than edit)
        solver_info = _make_solver_with_lastact(
            'solver_benoc.json',
            lastact_time=datetime(2026, 2, 11, 23, 19, 43),
        )
        mock_get_solver_by_id.return_value = solver_info

        # Test data - edit is OLDER than solver's last activity
        puzzle = load_fixture('puzzle_data.json')
        records = [
            {"solvername": "benoc", "timestamp": 1770850000}  # Earlier than lastact
        ]
        last_sheet_act_ts = 0

        # Test
        _process_activity_records(records, puzzle, last_sheet_act_ts, "test-thread", True)

        # Verify activity was recorded
        mock_record.assert_called_once()

        # Verify solver was NOT assigned (edit too old)
        mock_assign.assert_not_called()

    @patch('bigjimmybot.configstruct', {'BIGJIMMY_AUTOASSIGN': 'true'})
    @patch('bigjimmybot._get_solver_id')
    def test_process_activity_skips_bigjimmy(self, mock_get_solver):
        """Test that bot's own activity is skipped."""
        # Setup - should NOT call get_solver_id for bot activity
        mock_get_solver.return_value = 0

        # Test data with bot's activity
        puzzle = load_fixture('puzzle_data.json')
        records = [
            {"solvername": "bigjimmy", "timestamp": 1770860520}
        ]
        last_sheet_act_ts = 0

        # Test
        _process_activity_records(records, puzzle, last_sheet_act_ts, "test-thread", True)

        # Verify we never looked up the bot's solver ID
        mock_get_solver.assert_not_called()

    @patch('bigjimmybot.configstruct', {'BIGJIMMY_AUTOASSIGN': 'true'})
    @patch('bigjimmybot._get_solver_id')
    def test_process_activity_skips_unknown_solver(self, mock_get_solver):
        """Test that unknown solvers are skipped."""
        # Setup - solver not found
        mock_get_solver.return_value = 0

        # Test data
        puzzle = load_fixture('puzzle_data.json')
        records = [
            {"solvername": "unknownuser", "timestamp": 1770860446}
        ]
        last_sheet_act_ts = 0

        # Test
        _process_activity_records(records, puzzle, last_sheet_act_ts, "test-thread", True)

        # Verify solver lookup was attempted
        mock_get_solver.assert_called_once_with("unknownuser", "name")

    @patch('bigjimmybot.configstruct', {'BIGJIMMY_AUTOASSIGN': 'true'})
    @patch('bigjimmybot._get_solver_id')
    def test_process_activity_skips_old_sheet_activity(self, mock_get_solver):
        """Test that edits older than last sheet activity are skipped."""
        # Test data - edits are older than last_sheet_act_ts
        puzzle = load_fixture('puzzle_data.json')
        records = [
            {"solvername": "benoc", "timestamp": 1770860446}
        ]
        last_sheet_act_ts = 1770860500  # Newer than edit!

        # Test
        _process_activity_records(records, puzzle, last_sheet_act_ts, "test-thread", True)

        # Verify we never looked up solver (edit was too old)
        mock_get_solver.assert_not_called()


class TestFixtureValidity:
    """Ensure test fixtures are valid JSON and have expected structure."""

    def test_solver_fixtures_valid(self):
        """Test that solver fixtures are valid and have required fields."""
        solver_benoc = load_fixture('solver_benoc.json')
        assert solver_benoc['id'] == 456
        assert solver_benoc['name'] == 'benoc'
        assert solver_benoc['puzz'] == 'DifferentPuzzle'

        solver_assigned = load_fixture('solver_already_assigned.json')
        assert solver_assigned['puzz'] == 'TestPuzzle'

    def test_puzzle_fixture_valid(self):
        """Test that puzzle fixture is valid and has required fields."""
        puzzle = load_fixture('puzzle_data.json')
        assert puzzle['id'] == 123
        assert puzzle['name'] == 'FearlessThedeathdefyingJonnyGomes'
        assert 'sheetenabled' in puzzle
        assert 'sheetcount' in puzzle

    def test_sheet_activity_fixture_valid(self):
        """Test that sheet activity fixture is valid."""
        activity = load_fixture('sheet_activity_hidden.json')
        assert 'editors' in activity
        assert len(activity['editors']) == 3
        assert activity['editors'][0]['solvername'] == 'benoc'
        assert 'timestamp' in activity['editors'][0]
        assert activity['revision_count'] == 47
