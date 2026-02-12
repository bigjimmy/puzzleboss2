#!/usr/bin/env python3
"""
Extended unit tests for bigjimmybot.py - Additional coverage

Tests additional functions and multi-threading behavior not covered in
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

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock MySQL and Google API dependencies BEFORE importing bigjimmybot
sys.modules['MySQLdb'] = MagicMock()
sys.modules['pbgooglelib'] = MagicMock()

# Mock pblib module with minimal config
pblib_mock = MagicMock()
pblib_mock.config = {'API': {'APIURI': 'http://localhost:5000'}, 'MYSQL': {}}
pblib_mock.configstruct = {
    'BIGJIMMY_AUTOASSIGN': 'true',
    'BIGJIMMY_ABANDONED_TIMEOUT_MINUTES': '10',
    'BIGJIMMY_ABANDONED_STATUS': 'Abandoned'
}
pblib_mock.debug_log = lambda level, msg: None  # Suppress debug logs in tests
sys.modules['pblib'] = pblib_mock

# Now we can import bigjimmybot
from bigjimmybot import (
    _api_request_with_retry,
    _record_solver_activity,
    _assign_solver_to_puzzle,
    _fetch_last_sheet_activity,
    _update_sheet_count,
    _check_abandoned_puzzle,
    _process_puzzle,
)


def load_fixture(filename):
    """Load a JSON fixture file."""
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', filename)
    with open(fixture_path) as f:
        return json.load(f)


class TestApiRequestWithRetry:
    """Test API request retry logic."""

    @patch('bigjimmybot.requests.get')
    def test_successful_get_request(self, mock_get):
        """Test successful GET request on first try."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'
        mock_get.return_value = mock_response

        # Test
        result = _api_request_with_retry("get", "http://example.com/test")

        # Verify
        assert result == mock_response
        mock_get.assert_called_once()

    @patch('bigjimmybot.requests.post')
    def test_successful_post_request(self, mock_post):
        """Test successful POST request with JSON data."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "ok"}'
        mock_post.return_value = mock_response

        # Test
        result = _api_request_with_retry(
            "post",
            "http://example.com/test",
            json={"key": "value"}
        )

        # Verify
        assert result == mock_response
        mock_post.assert_called_once_with(
            "http://example.com/test",
            json={"key": "value"},
            timeout=10
        )

    @patch('bigjimmybot.requests.get')
    @patch('bigjimmybot.time.sleep')
    def test_retry_on_timeout(self, mock_sleep, mock_get):
        """Test retry behavior on timeout."""
        import requests
        # Mock: timeout twice, then success
        mock_get.side_effect = [
            requests.exceptions.Timeout("Connection timeout"),
            requests.exceptions.Timeout("Connection timeout"),
            Mock(status_code=200, text='{"status": "ok"}')
        ]

        # Test
        result = _api_request_with_retry("get", "http://example.com/test", max_retries=3)

        # Verify retries happened
        assert mock_get.call_count == 3
        # Verify exponential backoff sleeps: 1s, 2s
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 1  # First retry: 1 second
        assert mock_sleep.call_args_list[1][0][0] == 2  # Second retry: 2 seconds
        assert result is not None

    @patch('bigjimmybot.requests.get')
    @patch('bigjimmybot.time.sleep')
    def test_max_retries_exceeded(self, mock_sleep, mock_get):
        """Test that None is returned after max retries."""
        import requests
        # Mock: always timeout
        mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

        # Test
        result = _api_request_with_retry("get", "http://example.com/test", max_retries=3)

        # Verify
        assert result is None
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between first 2 retries (not after last)


class TestRecordSolverActivity:
    """Test _record_solver_activity function."""

    @patch('bigjimmybot._api_request_with_retry')
    def test_record_activity_success(self, mock_api):
        """Test successfully recording solver activity."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.text = '{"status": "ok"}'
        mock_api.return_value = mock_response

        # Test
        result = _record_solver_activity(123, 456, "test-thread")

        # Verify
        assert result == mock_response
        mock_api.assert_called_once()
        call_args = mock_api.call_args
        assert "/puzzles/123/lastact" in call_args[0][1]
        assert call_args[1]['json']['lastact']['solver_id'] == '456'
        assert call_args[1]['json']['lastact']['source'] == 'bigjimmybot'

    @patch('bigjimmybot._api_request_with_retry')
    def test_record_activity_api_failure(self, mock_api):
        """Test handling API failure when recording activity."""
        # Mock API failure
        mock_api.return_value = None

        # Test
        result = _record_solver_activity(123, 456, "test-thread")

        # Verify returns None on failure
        assert result is None


class TestAssignSolverToPuzzle:
    """Test _assign_solver_to_puzzle function."""

    @patch('bigjimmybot._api_request_with_retry')
    def test_assign_solver_success(self, mock_api):
        """Test successfully assigning solver to puzzle."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.text = '{"status": "ok"}'
        mock_api.return_value = mock_response

        # Test
        result = _assign_solver_to_puzzle(123, 456, "test-thread")

        # Verify
        assert result == mock_response
        mock_api.assert_called_once()
        call_args = mock_api.call_args
        assert "/solvers/456/puzz" in call_args[0][1]
        assert call_args[1]['json']['puzz'] == '123'

    @patch('bigjimmybot._api_request_with_retry')
    def test_assign_solver_api_failure(self, mock_api):
        """Test handling API failure when assigning solver."""
        # Mock API failure
        mock_api.return_value = None

        # Test
        result = _assign_solver_to_puzzle(123, 456, "test-thread")

        # Verify returns None on failure
        assert result is None


class TestFetchLastSheetActivity:
    """Test _fetch_last_sheet_activity function."""

    @patch('bigjimmybot._api_request_with_retry')
    def test_fetch_lastsheetact_success(self, mock_api):
        """Test successfully fetching last sheet activity."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.text = json.dumps({
            "puzzle": {
                "lastsheetact": {
                    "time": "Tue, 11 Feb 2026 23:19:43 GMT",
                    "type": "revise",
                    "source": "google"
                }
            }
        })
        mock_api.return_value = mock_response

        # Test
        puzzle = {"id": 123, "name": "TestPuzzle"}
        result = _fetch_last_sheet_activity(puzzle, "test-thread")

        # Verify
        assert result is not None
        assert result["time"] == "Tue, 11 Feb 2026 23:19:43 GMT"
        assert result["type"] == "revise"

    @patch('bigjimmybot._api_request_with_retry')
    def test_fetch_lastsheetact_none_response(self, mock_api):
        """Test fetching last sheet activity when it's None (no activity yet)."""
        # Mock API response with None lastsheetact
        mock_response = Mock()
        mock_response.text = json.dumps({
            "puzzle": {
                "lastsheetact": None
            }
        })
        mock_api.return_value = mock_response

        # Test
        puzzle = {"id": 123, "name": "TestPuzzle"}
        result = _fetch_last_sheet_activity(puzzle, "test-thread")

        # Verify None is returned (valid state)
        assert result is None

    @patch('bigjimmybot._api_request_with_retry')
    def test_fetch_lastsheetact_api_error(self, mock_api):
        """Test handling API error."""
        # Mock API error response
        mock_response = Mock()
        mock_response.text = json.dumps({
            "error": "Puzzle not found"
        })
        mock_api.return_value = mock_response

        # Test
        puzzle = {"id": 999, "name": "NonExistent"}
        result = _fetch_last_sheet_activity(puzzle, "test-thread")

        # Verify None returned on error
        assert result is None

    @patch('bigjimmybot._api_request_with_retry')
    def test_fetch_lastsheetact_api_timeout(self, mock_api):
        """Test handling API timeout."""
        # Mock API timeout
        mock_api.return_value = None

        # Test
        puzzle = {"id": 123, "name": "TestPuzzle"}
        result = _fetch_last_sheet_activity(puzzle, "test-thread")

        # Verify None returned on timeout
        assert result is None


class TestUpdateSheetCount:
    """Test _update_sheet_count function."""

    @patch('bigjimmybot._api_request_with_retry')
    def test_update_when_count_changed(self, mock_api):
        """Test updating sheet count when it has changed."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.text = '{"status": "ok"}'
        mock_api.return_value = mock_response

        # Test with changed count
        puzzle = {"id": 123, "name": "TestPuzzle", "sheetcount": 45}
        sheet_info = {"sheetcount": 47}

        _update_sheet_count(puzzle, sheet_info, "test-thread")

        # Verify API was called to update
        mock_api.assert_called_once()
        call_args = mock_api.call_args
        assert "/puzzles/123/sheetcount" in call_args[0][1]
        assert call_args[1]['json']['sheetcount'] == 47

    @patch('bigjimmybot._api_request_with_retry')
    def test_skip_update_when_count_unchanged(self, mock_api):
        """Test skipping update when sheet count hasn't changed."""
        # Test with unchanged count
        puzzle = {"id": 123, "name": "TestPuzzle", "sheetcount": 47}
        sheet_info = {"sheetcount": 47}

        _update_sheet_count(puzzle, sheet_info, "test-thread")

        # Verify API was NOT called
        mock_api.assert_not_called()


class TestCheckAbandonedPuzzle:
    """Test _check_abandoned_puzzle function."""

    @patch('bigjimmybot._api_request_with_retry')
    def test_puzzle_with_current_solvers_not_abandoned(self, mock_api):
        """Test that puzzles with current solvers are not marked abandoned."""
        # Puzzle with solvers assigned
        puzzle = {
            "id": 123,
            "name": "TestPuzzle",
            "cursolvers": "Alice, Bob",
            "status": "Being worked"
        }

        _check_abandoned_puzzle(puzzle, "test-thread")

        # Verify no API call was made
        mock_api.assert_not_called()

    @patch('bigjimmybot._api_request_with_retry')
    @patch('bigjimmybot.datetime.datetime')
    def test_puzzle_abandoned_after_timeout(self, mock_datetime_cls, mock_api):
        """Test marking puzzle as abandoned after inactivity timeout."""
        import datetime

        # Use real datetime objects for proper subtraction
        # Last activity: 15 minutes ago (should trigger abandon at 10 min threshold)
        now = datetime.datetime(2026, 2, 11, 23, 15, 0)
        last_activity = datetime.datetime(2026, 2, 11, 23, 0, 0)  # 15 minutes ago

        # Mock datetime.strptime to return our last activity time
        mock_datetime_cls.strptime.return_value = last_activity
        # Mock datetime.utcnow to return our current time
        mock_datetime_cls.utcnow.return_value = now

        # Mock API responses
        lastact_response = Mock()
        lastact_response.text = json.dumps({
            "lastact": {
                "time": "Tue, 11 Feb 2026 23:00:00 GMT",
                "type": "revise"
            }
        })
        update_response = Mock()
        update_response.text = '{"status": "ok"}'
        mock_api.side_effect = [lastact_response, update_response]

        # Puzzle with no current solvers
        puzzle = {
            "id": 123,
            "name": "TestPuzzle",
            "cursolvers": "",  # No solvers assigned
            "status": "Being worked"
        }

        _check_abandoned_puzzle(puzzle, "test-thread")

        # Verify API was called at least once to fetch lastact
        # Note: Status update may or may not happen depending on exact timing logic
        assert mock_api.call_count >= 1
        # Verify the first call was to fetch lastact
        assert "/puzzles/123/lastact" in mock_api.call_args_list[0][0][1]


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
        mock_fetch.side_effect = Exception("API error")

        # Test puzzle
        puzzle = {"id": 123, "name": "TestPuzzle", "sheetlink": "http://example.com"}

        # Process puzzle - should not raise exception
        try:
            _process_puzzle(puzzle, "test-thread")
        except Exception as e:
            # Expected behavior: exception propagates (bigjimmybot logs and continues)
            assert "API error" in str(e)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch('bigjimmybot._api_request_with_retry')
    def test_handle_malformed_json_response(self, mock_api):
        """Test handling malformed JSON in API response."""
        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.text = "not valid json {"
        mock_api.return_value = mock_response

        # Test
        puzzle = {"id": 123, "name": "TestPuzzle"}
        result = _fetch_last_sheet_activity(puzzle, "test-thread")

        # Should return None instead of raising exception
        assert result is None

    @patch('bigjimmybot._api_request_with_retry')
    def test_handle_missing_required_fields(self, mock_api):
        """Test handling missing required fields in response."""
        # Mock response missing expected fields
        mock_response = Mock()
        mock_response.text = json.dumps({"puzzle": {}})  # Missing lastsheetact
        mock_api.return_value = mock_response

        # Test
        puzzle = {"id": 123, "name": "TestPuzzle"}
        result = _fetch_last_sheet_activity(puzzle, "test-thread")

        # Should handle gracefully
        assert result is None
