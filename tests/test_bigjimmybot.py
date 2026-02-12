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
sys.modules['pbgooglelib'] = MagicMock()

# Mock pblib module with minimal config
pblib_mock = MagicMock()
pblib_mock.config = {'API': {'APIURI': 'http://localhost:5000'}, 'MYSQL': {}}
pblib_mock.configstruct = {'BIGJIMMY_AUTOASSIGN': 'true'}
pblib_mock.debug_log = lambda level, msg: None  # Suppress debug logs in tests
sys.modules['pblib'] = pblib_mock

# Now we can import bigjimmybot
from bigjimmybot import (
    _parse_api_timestamp,
    _parse_revision_timestamp,
    _get_solver_id,
    _process_activity_records,
)


def load_fixture(filename):
    """Load a JSON fixture file."""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', filename)
    with open(fixture_path) as f:
        return json.load(f)


class TestTimestampParsing:
    """Test timestamp parsing functions."""

    def test_parse_api_timestamp_valid(self):
        """Test parsing valid API timestamp (MySQL format)."""
        timestamp = "Tue, 11 Feb 2026 23:19:43 GMT"
        result = _parse_api_timestamp(timestamp)
        # Expected: Feb 11, 2026 23:19:43 UTC
        assert result == 1770855583

    def test_parse_revision_timestamp_valid(self):
        """Test parsing valid Google Drive revision timestamp."""
        timestamp = "2026-02-12T01:40:46.123Z"
        result = _parse_revision_timestamp(timestamp)
        # Expected: Feb 12, 2026 01:40:46.123 UTC
        # Note: function preserves milliseconds, returns float
        assert int(result) == 1770860446


class TestSolverLookup:
    """Test solver lookup with mocked API."""

    @patch('bigjimmybot._api_request_with_retry')
    def test_get_solver_id_by_name_found(self, mock_api):
        """Test successful solver lookup by name."""
        # Mock API response
        solver_data = load_fixture('solver_benoc.json')
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(solver_data)
        mock_api.return_value = mock_response

        # Test
        result = _get_solver_id("benoc", "name")

        # Verify
        assert result == 456
        mock_api.assert_called_once()
        call_args = mock_api.call_args[0]
        assert call_args[0] == "get"
        assert "byname/benoc" in call_args[1]

    @patch('bigjimmybot._api_request_with_retry')
    def test_get_solver_id_by_email_found(self, mock_api):
        """Test successful solver lookup by email (extracts username)."""
        # Mock API response
        solver_data = load_fixture('solver_benoc.json')
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(solver_data)
        mock_api.return_value = mock_response

        # Test with full email
        result = _get_solver_id("benoc@example.com", "email")

        # Verify - should extract "benoc" from email
        assert result == 456
        call_args = mock_api.call_args[0]
        assert "byname/benoc" in call_args[1]

    @patch('bigjimmybot._api_request_with_retry')
    def test_get_solver_id_not_found_404(self, mock_api):
        """Test solver lookup when solver doesn't exist (404 response)."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_api.return_value = mock_response

        # Test
        result = _get_solver_id("nonexistent", "name")

        # Verify returns 0 for not found
        assert result == 0

    @patch('bigjimmybot._api_request_with_retry')
    def test_get_solver_id_api_error(self, mock_api):
        """Test solver lookup when API returns error."""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = json.dumps({
            "status": "error",
            "error": "Solver 'invalid' not found"
        })
        mock_api.return_value = mock_response

        # Test
        result = _get_solver_id("invalid", "name")

        # Verify returns 0 for error
        assert result == 0

    @patch('bigjimmybot._api_request_with_retry')
    def test_get_solver_id_api_timeout(self, mock_api):
        """Test solver lookup when API times out."""
        # Mock timeout (no response)
        mock_api.return_value = None

        # Test
        result = _get_solver_id("benoc", "name")

        # Verify returns 0 for timeout
        assert result == 0

    @patch('bigjimmybot._api_request_with_retry')
    def test_get_solver_id_case_insensitive(self, mock_api):
        """Test solver lookup is case-insensitive."""
        # Mock API response
        solver_data = load_fixture('solver_benoc.json')
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = json.dumps(solver_data)
        mock_api.return_value = mock_response

        # Test with different cases
        result1 = _get_solver_id("BENOC", "name")
        result2 = _get_solver_id("BeNoC", "name")

        # Verify both work
        assert result1 == 456
        assert result2 == 456
        # Verify both were lowercased in API call
        assert "byname/benoc" in mock_api.call_args_list[0][0][1]
        assert "byname/benoc" in mock_api.call_args_list[1][0][1]


class TestActivityProcessing:
    """Test activity record processing logic."""

    @patch('bigjimmybot.configstruct', {'BIGJIMMY_AUTOASSIGN': 'true'})
    @patch('bigjimmybot._assign_solver_to_puzzle')
    @patch('bigjimmybot._record_solver_activity')
    @patch('bigjimmybot._api_request_with_retry')
    @patch('bigjimmybot._get_solver_id')
    def test_process_activity_assigns_new_solver(
        self, mock_get_solver, mock_api, mock_record, mock_assign
    ):
        """Test that new activity triggers solver assignment."""
        # Setup mocks
        mock_get_solver.return_value = 456  # benoc's ID

        # Mock solver info response - on different puzzle
        solver_data = load_fixture('solver_benoc.json')
        mock_response = Mock()
        mock_response.text = json.dumps(solver_data)
        mock_api.return_value = mock_response

        # Test data
        puzzle = load_fixture('puzzle_data.json')
        records = [
            {"solvername": "benoc", "timestamp": 1770860446}
        ]
        last_sheet_act_ts = 0  # No previous activity

        # Test
        _process_activity_records(records, puzzle, last_sheet_act_ts, "test-thread", True)

        # Verify activity was recorded
        mock_record.assert_called_once_with(123, 456, "test-thread")

        # Verify solver was assigned
        mock_assign.assert_called_once_with(123, 456, "test-thread")

    @patch('bigjimmybot.configstruct', {'BIGJIMMY_AUTOASSIGN': 'true'})
    @patch('bigjimmybot._assign_solver_to_puzzle')
    @patch('bigjimmybot._record_solver_activity')
    @patch('bigjimmybot._api_request_with_retry')
    @patch('bigjimmybot._get_solver_id')
    def test_process_activity_skips_already_assigned(
        self, mock_get_solver, mock_api, mock_record, mock_assign
    ):
        """Test that already-assigned solver is skipped for assignment."""
        # Setup mocks
        mock_get_solver.return_value = 456

        # Mock solver already on this puzzle
        solver_data = load_fixture('solver_already_assigned.json')
        mock_response = Mock()
        mock_response.text = json.dumps(solver_data)
        mock_api.return_value = mock_response

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
    @patch('bigjimmybot._api_request_with_retry')
    @patch('bigjimmybot._get_solver_id')
    def test_process_activity_respects_autoassign_disabled(
        self, mock_get_solver, mock_api, mock_record, mock_assign
    ):
        """Test that auto-assign is skipped when disabled."""
        # Setup mocks
        mock_get_solver.return_value = 456

        # Mock solver info
        solver_data = load_fixture('solver_benoc.json')
        mock_response = Mock()
        mock_response.text = json.dumps(solver_data)
        mock_api.return_value = mock_response

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
    @patch('bigjimmybot._api_request_with_retry')
    @patch('bigjimmybot._get_solver_id')
    def test_process_activity_skips_old_edit(
        self, mock_get_solver, mock_api, mock_record, mock_assign
    ):
        """Test that edit older than solver's last activity is skipped."""
        # Setup mocks
        mock_get_solver.return_value = 456

        # Mock solver with recent activity
        solver_data = load_fixture('solver_benoc.json')
        mock_response = Mock()
        mock_response.text = json.dumps(solver_data)
        mock_api.return_value = mock_response

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
        assert solver_benoc['status'] == 'ok'
        assert 'solver' in solver_benoc
        assert solver_benoc['solver']['id'] == 456
        assert solver_benoc['solver']['name'] == 'benoc'
        assert 'lastact' in solver_benoc['solver']

        solver_assigned = load_fixture('solver_already_assigned.json')
        assert solver_assigned['solver']['puzz'] == 'TestPuzzle'

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
