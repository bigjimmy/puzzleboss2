#!/usr/bin/env python3
"""
Unit tests for the Google API rate limiter in pbgooglelib.py.

Tests the _GoogleApiRateLimiter class without requiring Google API credentials
or any network access.

Run with: pytest tests/test_rate_limiter.py -v
"""

import pytest
import time
import threading
import os
import sys
import importlib
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock heavy dependencies BEFORE importing pbgooglelib
sys.modules['MySQLdb'] = MagicMock()
sys.modules['MySQLdb.cursors'] = MagicMock()

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
pblib_mock.configstruct = {
    'BIGJIMMY_GOOGLE_API_QPM': '55',
}
pblib_mock.debug_log = lambda level, msg: None
sys.modules['pblib'] = pblib_mock

# If pbgooglelib was previously replaced with a MagicMock (by bigjimmybot tests),
# we need to remove it so the real module gets loaded.
if 'pbgooglelib' in sys.modules and isinstance(sys.modules['pbgooglelib'], MagicMock):
    del sys.modules['pbgooglelib']

import pbgooglelib
importlib.reload(pbgooglelib)
from pbgooglelib import _GoogleApiRateLimiter, _DEFAULT_QPM


class TestRateLimiterBasics:
    """Test basic rate limiter behavior."""

    def test_first_acquire_is_immediate(self):
        """First acquire() call should not sleep."""
        limiter = _GoogleApiRateLimiter()
        with patch('pbgooglelib.time') as mock_time:
            mock_time.time.return_value = 1000.0
            mock_time.sleep = MagicMock()

            limiter.acquire()

            # First call should not sleep
            mock_time.sleep.assert_not_called()

    def test_second_acquire_sleeps(self):
        """Second acquire() should sleep for the minimum interval."""
        limiter = _GoogleApiRateLimiter()
        with patch('pbgooglelib.time') as mock_time:
            # Both calls happen at same "now" to force a wait
            mock_time.time.return_value = 1000.0
            mock_time.sleep = MagicMock()

            limiter.acquire()  # Immediate
            limiter.acquire()  # Should sleep

            expected_interval = 60.0 / 55  # ~1.09s at 55 QPM
            mock_time.sleep.assert_called_once()
            actual_wait = mock_time.sleep.call_args[0][0]
            assert abs(actual_wait - expected_interval) < 0.01

    def test_no_sleep_when_enough_time_passed(self):
        """If enough time passes between calls, second call is immediate."""
        limiter = _GoogleApiRateLimiter()
        with patch('pbgooglelib.time') as mock_time:
            mock_time.sleep = MagicMock()

            # First call at t=1000
            mock_time.time.return_value = 1000.0
            limiter.acquire()

            # Second call at t=1005 (5 seconds later — well past interval)
            mock_time.time.return_value = 1005.0
            limiter.acquire()

            # Neither call should have slept
            mock_time.sleep.assert_not_called()

    def test_slot_spacing_three_rapid_calls(self):
        """Three rapid calls should space out with increasing wait times."""
        limiter = _GoogleApiRateLimiter()
        waits = []
        with patch('pbgooglelib.time') as mock_time:
            mock_time.time.return_value = 1000.0
            mock_time.sleep = MagicMock(side_effect=lambda t: waits.append(t))

            limiter.acquire()  # Immediate
            limiter.acquire()  # Wait ~1.09s
            limiter.acquire()  # Wait ~2.18s

            interval = 60.0 / 55
            assert len(waits) == 2
            assert abs(waits[0] - interval) < 0.01
            assert abs(waits[1] - 2 * interval) < 0.01


class TestRateLimiterConfig:
    """Test that rate limiter respects configuration."""

    def test_uses_config_qpm(self):
        """Rate limiter reads QPM from configstruct."""
        limiter = _GoogleApiRateLimiter()
        with patch('pbgooglelib.time') as mock_time:
            mock_time.time.return_value = 1000.0
            mock_time.sleep = MagicMock()

            # Set QPM to 30 (slower rate)
            with patch('pbgooglelib.configstruct', {'BIGJIMMY_GOOGLE_API_QPM': '30'}):
                limiter.acquire()
                limiter.acquire()

            expected_interval = 60.0 / 30  # 2.0s
            actual_wait = mock_time.sleep.call_args[0][0]
            assert abs(actual_wait - expected_interval) < 0.01

    def test_uses_default_qpm_when_not_configured(self):
        """Rate limiter falls back to _DEFAULT_QPM when config is missing."""
        limiter = _GoogleApiRateLimiter()
        with patch('pbgooglelib.time') as mock_time:
            mock_time.time.return_value = 1000.0
            mock_time.sleep = MagicMock()

            with patch('pbgooglelib.configstruct', {}):
                limiter.acquire()
                limiter.acquire()

            expected_interval = 60.0 / _DEFAULT_QPM
            actual_wait = mock_time.sleep.call_args[0][0]
            assert abs(actual_wait - expected_interval) < 0.01

    def test_qpm_of_one_gives_60s_interval(self):
        """QPM=1 means one call per minute."""
        limiter = _GoogleApiRateLimiter()
        with patch('pbgooglelib.time') as mock_time:
            mock_time.time.return_value = 1000.0
            mock_time.sleep = MagicMock()

            with patch('pbgooglelib.configstruct', {'BIGJIMMY_GOOGLE_API_QPM': '1'}):
                limiter.acquire()
                limiter.acquire()

            actual_wait = mock_time.sleep.call_args[0][0]
            assert abs(actual_wait - 60.0) < 0.01

    def test_qpm_zero_treated_as_one(self):
        """QPM=0 should not cause division by zero — treated as 1."""
        limiter = _GoogleApiRateLimiter()
        with patch('pbgooglelib.time') as mock_time:
            mock_time.time.return_value = 1000.0
            mock_time.sleep = MagicMock()

            with patch('pbgooglelib.configstruct', {'BIGJIMMY_GOOGLE_API_QPM': '0'}):
                limiter.acquire()
                limiter.acquire()

            # max(0, 1) = 1, so interval = 60s
            actual_wait = mock_time.sleep.call_args[0][0]
            assert abs(actual_wait - 60.0) < 0.01


class TestRateLimiterThreadSafety:
    """Test that rate limiter is thread-safe."""

    def test_concurrent_acquires_all_complete(self):
        """Multiple threads calling acquire() should all complete without error."""
        limiter = _GoogleApiRateLimiter()
        errors = []
        completed = []
        lock = threading.Lock()

        def worker(i):
            try:
                limiter.acquire()
                with lock:
                    completed.append(i)
            except Exception as e:
                with lock:
                    errors.append(e)

        # Use a high QPM for fast test execution
        with patch('pbgooglelib.configstruct', {'BIGJIMMY_GOOGLE_API_QPM': '6000'}):
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

        assert len(errors) == 0
        assert len(completed) == 10

    def test_next_slot_advances_under_contention(self):
        """Under contention, _next_slot should advance past the starting point."""
        limiter = _GoogleApiRateLimiter()
        barrier = threading.Barrier(20)

        def worker():
            barrier.wait()  # Ensure all threads start simultaneously
            limiter.acquire()

        start_time = time.time()
        with patch('pbgooglelib.configstruct', {'BIGJIMMY_GOOGLE_API_QPM': '6000'}):
            threads = [threading.Thread(target=worker) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

        # After 20 concurrent acquires at 6000 QPM (0.01s interval),
        # _next_slot should have advanced at least 19 intervals from start
        interval = 60.0 / 6000
        assert limiter._next_slot > start_time + 19 * interval


class TestDefaultQpmConstant:
    """Test the _DEFAULT_QPM constant."""

    def test_default_qpm_is_conservative(self):
        """Default QPM should be under the hard 60 QPM limit."""
        assert _DEFAULT_QPM < 60
        assert _DEFAULT_QPM > 0

    def test_default_qpm_value(self):
        """Default QPM should be 55 (5 below the 60 QPM hard limit)."""
        assert _DEFAULT_QPM == 55
