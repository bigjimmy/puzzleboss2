"""Unit tests for pblib's cache-facing logic: the structural-invalidation
allowlist, the lastact write-through, and activity serialization.

These guard the core of the Redis write-through design:
  - update_puzzle_field invalidates the /all blob ONLY for structural fields,
    so high-churn fields (xyzloc, comments, sheetcount) ride the TTL instead
    of coupling cache lifetime to write frequency.
  - log_activity writes through to the lastact hash, but only when Redis is
    live (no extra DB work when caching is off).
  - serialize_activity makes a datetime row JSON-safe.
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest

import pblib


@pytest.fixture(autouse=True)
def quiet_logs():
    with patch("pblib.debug_log"):
        yield


def _conn():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


# ── STRUCTURAL_PUZZLE_FIELDS invalidation allowlist ───────────────────────


class TestStructuralAllowlist:
    """update_puzzle_field invalidates the blob iff the field is structural."""

    STRUCTURAL = ["status", "name", "round_id", "answer", "ismeta"]
    NON_STRUCTURAL = ["xyzloc", "comments", "sheetcount"]

    @pytest.mark.parametrize("field", STRUCTURAL)
    def test_structural_field_invalidates(self, field):
        conn, cursor = _conn()
        # status logs activity (write-through); stub it out to isolate.
        with patch("pblib._invalidate_cache") as inval, patch("pblib.log_activity"):
            # 'answer' has no special path; a plain value works for all.
            pblib.update_puzzle_field(287, field, "x", conn, source="test")
        inval.assert_called_once_with(conn)

    @pytest.mark.parametrize("field", NON_STRUCTURAL)
    def test_non_structural_field_does_not_invalidate(self, field):
        conn, cursor = _conn()
        with patch("pblib._invalidate_cache") as inval, patch("pblib.log_activity"):
            pblib.update_puzzle_field(287, field, "x", conn, source="test")
        inval.assert_not_called()

    def test_status_change_still_logs_activity(self):
        # The allowlist change must not break status activity logging.
        conn, cursor = _conn()
        with patch("pblib._invalidate_cache"), patch("pblib.log_activity") as log:
            pblib.update_puzzle_field(287, "status", "Needs eyes", conn, source="test")
        log.assert_called_once_with(287, "status", 100, "test", conn)

    def test_solved_status_does_not_double_log(self):
        # 'Solved' is logged as 'solve' elsewhere; status path must skip it.
        conn, cursor = _conn()
        with patch("pblib._invalidate_cache"), patch("pblib.log_activity") as log:
            pblib.update_puzzle_field(287, "status", "Solved", conn, source="test")
        log.assert_not_called()

    def test_allowlist_membership(self):
        # Pin the exact set so an accidental add/remove is caught.
        assert pblib.STRUCTURAL_PUZZLE_FIELDS == {
            "status", "name", "round_id", "answer", "ismeta"
        }


# ── lastact write-through in log_activity ─────────────────────────────────


class TestWriteThrough:
    def test_noop_when_redis_disabled(self):
        # With Redis off, log_activity must do NO extra DB query for
        # write-through — only the INSERT. This guards the "zero extra cost
        # when caching is off" claim (prod before cutover, every bot revise).
        conn, cursor = _conn()
        with patch("pbcachelib.rc", None), patch(
            "pbcachelib.ensure_cache_initialized"
        ), patch("pblib.get_last_activity_for_puzzle") as glap:
            ok = pblib.log_activity(287, "revise", 101, "bigjimmybot", conn)
        assert ok is True
        glap.assert_not_called()  # no re-query when Redis is down

    def test_writes_through_when_redis_live(self):
        conn, cursor = _conn()
        row = {"id": 9, "puzzle_id": 287, "type": "revise",
               "time": datetime.datetime(2026, 1, 1, 12, 0, 0)}
        with patch("pbcachelib.rc", MagicMock()), patch(
            "pbcachelib.ensure_cache_initialized"
        ), patch(
            "pblib.get_last_activity_for_puzzle", return_value=row
        ), patch("pbcachelib.lastact_set") as lset:
            pblib.log_activity(287, "revise", 101, "bigjimmybot", conn)
        lset.assert_called_once()
        pid_arg, row_arg = lset.call_args[0]
        assert pid_arg == 287
        # time must have been serialized to an ISO string before caching.
        assert row_arg["time"] == "2026-01-01T12:00:00"

    def test_writethrough_failure_does_not_break_logging(self):
        # A cache error during write-through must not fail the activity log.
        conn, cursor = _conn()
        with patch("pbcachelib.rc", MagicMock()), patch(
            "pbcachelib.ensure_cache_initialized"
        ), patch(
            "pblib.get_last_activity_for_puzzle", side_effect=RuntimeError("redis gone")
        ):
            ok = pblib.log_activity(287, "revise", 101, "bigjimmybot", conn)
        assert ok is True  # INSERT committed; write-through error swallowed

    def test_insert_failure_returns_false_no_writethrough(self):
        conn, cursor = _conn()
        cursor.execute.side_effect = RuntimeError("db down")
        with patch("pblib.get_last_activity_for_puzzle") as glap:
            ok = pblib.log_activity(287, "revise", 101, "bigjimmybot", conn)
        assert ok is False
        glap.assert_not_called()  # never write through a failed insert


# ── serialize_activity ────────────────────────────────────────────────────


class TestSerializeActivity:
    def test_datetime_to_iso(self):
        row = {"id": 1, "time": datetime.datetime(2026, 3, 29, 21, 13, 27)}
        out = pblib.serialize_activity(row)
        assert out["time"] == "2026-03-29T21:13:27"
        assert isinstance(out["time"], str)

    def test_does_not_mutate_input(self):
        ts = datetime.datetime(2026, 3, 29, 21, 13, 27)
        row = {"id": 1, "time": ts}
        pblib.serialize_activity(row)
        assert row["time"] is ts  # original untouched (returns a copy)

    def test_none_passthrough(self):
        assert pblib.serialize_activity(None) is None

    def test_empty_time_passthrough(self):
        row = {"id": 1, "time": None}
        assert pblib.serialize_activity(row) == row
