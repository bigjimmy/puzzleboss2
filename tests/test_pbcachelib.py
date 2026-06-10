"""Unit tests for pbcachelib — the Redis cache layer.

These tests use a MagicMock in place of the Redis client (pbcachelib.rc),
so they run with no Redis present and no new dependencies. They cover the
two properties the rest of the system relies on:

  1. Fail-safe contract — every operation is a safe no-op / safe default
     both when caching is disabled (rc is None) and when the client raises.
     This is the "Redis down → fall back to DB, never error the request"
     guarantee.
  2. Data semantics — JSON round-tripping, integer key coercion (the
     integer-ID convention), the None-vs-{} distinction in lastact_get_all,
     and the SET NX lock contract.

Real Redis command semantics (actual HSET/SET-NX behavior) are covered by
the integration tests in scripts/test_api_coverage.py against the Docker
Redis container.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

import pbcachelib


@pytest.fixture
def mock_rc():
    """Patch pbcachelib.rc with a fresh MagicMock for the duration of a test."""
    client = MagicMock()
    with patch.object(pbcachelib, "rc", client):
        yield client


@pytest.fixture
def no_rc():
    """Patch pbcachelib.rc to None (caching disabled / Redis unreachable)."""
    with patch.object(pbcachelib, "rc", None):
        yield


# Silence debug_log so failures don't spam; it's exercised, just not asserted.
@pytest.fixture(autouse=True)
def quiet_logs():
    with patch("pbcachelib.debug_log"):
        yield


# ── Fail-safe: caching disabled (rc is None) ──────────────────────────────


class TestFailsafeDisabled:
    """With no client, every op is a safe no-op or safe default."""

    def test_cache_get_returns_none(self, no_rc):
        assert pbcachelib.cache_get("k") is None

    def test_cache_set_noop(self, no_rc):
        # Must not raise.
        pbcachelib.cache_set("k", "v")

    def test_cache_delete_noop(self, no_rc):
        pbcachelib.cache_delete("k")

    def test_lastact_set_noop(self, no_rc):
        pbcachelib.lastact_set(1, {"type": "create"})

    def test_lastact_get_all_returns_none(self, no_rc):
        # None (not {}) — lets callers distinguish "down" from "empty".
        assert pbcachelib.lastact_get_all() is None

    def test_lastact_get_returns_none(self, no_rc):
        assert pbcachelib.lastact_get(1) is None

    def test_lastact_delete_noop(self, no_rc):
        pbcachelib.lastact_delete(1)

    def test_lastact_set_many_noop(self, no_rc):
        pbcachelib.lastact_set_many({1: {"type": "create"}})

    def test_lock_acquire_failopen(self, no_rc):
        # With Redis down the lock fails open: everyone "rebuilds", same as
        # having no cache. Returning False here would deadlock /all forever.
        assert pbcachelib.try_acquire_rebuild_lock() is True

    def test_lock_release_noop(self, no_rc):
        pbcachelib.release_rebuild_lock()


# ── Fail-safe: client raises ──────────────────────────────────────────────


class TestFailsafeOnException:
    """If the live client raises, wrappers swallow and return safe defaults —
    a Redis blip must never escape as a 500."""

    def test_cache_get_swallows(self, mock_rc):
        mock_rc.get.side_effect = RuntimeError("connection reset")
        assert pbcachelib.cache_get("k") is None

    def test_cache_set_swallows(self, mock_rc):
        mock_rc.set.side_effect = RuntimeError("boom")
        pbcachelib.cache_set("k", "v")  # no raise

    def test_cache_delete_swallows(self, mock_rc):
        mock_rc.delete.side_effect = RuntimeError("boom")
        pbcachelib.cache_delete("k")

    def test_lastact_set_swallows(self, mock_rc):
        mock_rc.hset.side_effect = RuntimeError("boom")
        pbcachelib.lastact_set(1, {"type": "create"})

    def test_lastact_get_all_swallows(self, mock_rc):
        mock_rc.hgetall.side_effect = RuntimeError("boom")
        assert pbcachelib.lastact_get_all() is None

    def test_lastact_get_swallows(self, mock_rc):
        mock_rc.hget.side_effect = RuntimeError("boom")
        assert pbcachelib.lastact_get(1) is None

    def test_lastact_delete_swallows(self, mock_rc):
        mock_rc.hdel.side_effect = RuntimeError("boom")
        pbcachelib.lastact_delete(1)

    def test_lastact_set_many_swallows(self, mock_rc):
        mock_rc.hset.side_effect = RuntimeError("boom")
        pbcachelib.lastact_set_many({1: {"type": "create"}})

    def test_lock_acquire_failopen_on_exception(self, mock_rc):
        mock_rc.set.side_effect = RuntimeError("boom")
        assert pbcachelib.try_acquire_rebuild_lock() is True


# ── cache_get/set/delete contracts ────────────────────────────────────────


class TestCacheBlobOps:
    def test_cache_get_passes_key(self, mock_rc):
        mock_rc.get.return_value = "cached-value"
        assert pbcachelib.cache_get("puzzleboss:all") == "cached-value"
        mock_rc.get.assert_called_once_with("puzzleboss:all")

    def test_cache_set_uses_ttl(self, mock_rc):
        pbcachelib.cache_set("puzzleboss:all", "blob", ttl=15)
        mock_rc.set.assert_called_once_with("puzzleboss:all", "blob", ex=15)

    def test_cache_set_default_ttl(self, mock_rc):
        pbcachelib.cache_set("k", "v")
        _, kwargs = mock_rc.set.call_args
        assert kwargs["ex"] == pbcachelib.CACHE_TTL

    def test_cache_delete_passes_key(self, mock_rc):
        pbcachelib.cache_delete("puzzleboss:all")
        mock_rc.delete.assert_called_once_with("puzzleboss:all")


# ── lastact hash semantics ────────────────────────────────────────────────


class TestLastactHash:
    def test_set_encodes_json_with_string_int_key(self, mock_rc):
        row = {"id": 9, "puzzle_id": 42, "type": "revise", "time": "2026-01-01T00:00:00"}
        pbcachelib.lastact_set(42, row)
        mock_rc.hset.assert_called_once()
        args = mock_rc.hset.call_args[0]
        assert args[0] == pbcachelib.LASTACT_KEY
        assert args[1] == "42"  # field is str(int(pid))
        assert json.loads(args[2]) == row  # value is JSON

    def test_set_coerces_string_pid(self, mock_rc):
        # Integer-ID convention: a string pid is normalized to str(int(pid)).
        pbcachelib.lastact_set("042", {"type": "create"})
        assert mock_rc.hset.call_args[0][1] == "42"

    def test_get_all_decodes_to_int_keyed_dict(self, mock_rc):
        mock_rc.hgetall.return_value = {
            "1": json.dumps({"id": 5, "type": "create"}),
            "42": json.dumps({"id": 9, "type": "revise"}),
        }
        result = pbcachelib.lastact_get_all()
        assert result == {1: {"id": 5, "type": "create"}, 42: {"id": 9, "type": "revise"}}
        # Keys are ints, not strings (so callers can match puzzle["id"]).
        assert all(isinstance(k, int) for k in result)

    def test_get_all_empty_returns_empty_dict_not_none(self, mock_rc):
        # Redis up but hash empty → {} (distinct from None = Redis down).
        mock_rc.hgetall.return_value = {}
        assert pbcachelib.lastact_get_all() == {}

    def test_get_single_decodes(self, mock_rc):
        mock_rc.hget.return_value = json.dumps({"id": 9, "type": "revise"})
        assert pbcachelib.lastact_get(42) == {"id": 9, "type": "revise"}
        mock_rc.hget.assert_called_once_with(pbcachelib.LASTACT_KEY, "42")

    def test_get_single_missing_returns_none(self, mock_rc):
        mock_rc.hget.return_value = None
        assert pbcachelib.lastact_get(42) is None

    def test_delete_passes_string_field(self, mock_rc):
        pbcachelib.lastact_delete(42)
        mock_rc.hdel.assert_called_once_with(pbcachelib.LASTACT_KEY, "42")

    def test_set_many_builds_mapping(self, mock_rc):
        rows = {1: {"type": "create"}, 2: {"type": "revise"}}
        pbcachelib.lastact_set_many(rows)
        _, kwargs = mock_rc.hset.call_args
        mapping = kwargs["mapping"]
        assert set(mapping) == {"1", "2"}
        assert json.loads(mapping["1"]) == {"type": "create"}

    def test_set_many_empty_is_noop(self, mock_rc):
        pbcachelib.lastact_set_many({})
        mock_rc.hset.assert_not_called()


# ── rebuild lock ──────────────────────────────────────────────────────────


class TestRebuildLock:
    def test_acquire_uses_set_nx_with_ttl(self, mock_rc):
        mock_rc.set.return_value = True
        assert pbcachelib.try_acquire_rebuild_lock() is True
        mock_rc.set.assert_called_once_with(
            pbcachelib.LOCK_KEY, "1", nx=True, ex=pbcachelib.LOCK_TTL
        )

    def test_acquire_returns_false_when_held(self, mock_rc):
        # redis SET NX returns None when the key already exists.
        mock_rc.set.return_value = None
        assert pbcachelib.try_acquire_rebuild_lock() is False

    def test_release_deletes_lock_key(self, mock_rc):
        pbcachelib.release_rebuild_lock()
        mock_rc.delete.assert_called_once_with(pbcachelib.LOCK_KEY)


# ── invalidate_all_cache: deletion + observability ───────────────────────


class TestInvalidateAllCache:
    def test_deletes_blob_and_counts(self, mock_rc):
        conn = MagicMock()
        with patch("pbcachelib.increment_botstat") as inc, patch(
            "pbcachelib.ensure_cache_initialized"
        ):
            pbcachelib.invalidate_all_cache(conn)
        mock_rc.delete.assert_called_once_with(pbcachelib.CACHE_KEY)
        inc.assert_called_once_with("cache_invalidations_total", conn)

    def test_stats_failure_does_not_block_delete(self, mock_rc):
        # The counter is fail-safe: a botstat error must not stop the
        # invalidation. increment_botstat already swallows internally; here we
        # assert the delete still happens even if it were to raise.
        conn = MagicMock()
        with patch(
            "pbcachelib.increment_botstat", side_effect=RuntimeError("stats down")
        ), patch("pbcachelib.ensure_cache_initialized"):
            try:
                pbcachelib.invalidate_all_cache(conn)
            except RuntimeError:
                pytest.fail("invalidate_all_cache let a stats error escape")
        mock_rc.delete.assert_called_once_with(pbcachelib.CACHE_KEY)
