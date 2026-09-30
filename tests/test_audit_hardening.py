"""Regression tests for the September audit's remaining high findings.

- POST /config must not log the value of a key that is already secret,
  even when the write omits the `secret` field (how secrets get rotated).
- GET /puzzles/<id> returns 404 for a missing puzzle, not ok/null.
- The per-thread Google HTTP client has a socket timeout, so a hung call
  can't stall a bigjimmy thread forever.

The Revisions-path timestamp truncation is covered in test_bigjimmybot.py.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest


class _OperationalError(Exception):
    """Stands in for MySQLdb.OperationalError, which is stubbed in unit tests."""


class _FakeCursor:
    """Records SQL; answers the secret-flag lookup from a dict."""

    def __init__(self, flags, missing_column=False):
        self.flags = flags
        self.missing_column = missing_column
        self.rowcount = 1
        self._row = None

    def execute(self, sql, params=()):
        if sql.startswith("SELECT `secret` FROM config"):
            if self.missing_column:
                raise _OperationalError(1054, "Unknown column 'secret'")
            key = params[0]
            self._row = {"secret": self.flags[key]} if key in self.flags else None
        else:
            self._row = None

    def fetchone(self):
        return self._row


def _post_config(pbrest, client, body, cursor):
    logged = []
    conn = MagicMock()
    with patch.dict(pbrest.configstruct, {"ADMIN_TOKEN_ENFORCE": "false"}), \
         patch.object(pbrest, "_cursor", lambda: (conn, cursor)), \
         patch.object(pbrest, "debug_log", lambda sev, msg: logged.append(msg)):
        resp = client.post("/config", json=body)
    assert resp.status_code == 200, resp.get_json()
    return "\n".join(logged)


class TestConfigWriteLogging:
    VALUE = "s3kr1t-value-do-not-log"

    def test_value_only_write_to_flagged_key_is_redacted(self, pbrest, client):
        # Name matches no heuristic pattern; only the stored flag marks it
        log = _post_config(
            pbrest, client,
            {"cfgkey": "HUNT_PORTAL_CREDS", "cfgval": self.VALUE},
            _FakeCursor({"HUNT_PORTAL_CREDS": 1}),
        )
        assert self.VALUE not in log
        assert "<redacted>" in log

    def test_value_only_write_to_heuristic_key_is_redacted(self, pbrest, client):
        log = _post_config(
            pbrest, client,
            {"cfgkey": "GEMINI_API_KEY", "cfgval": self.VALUE},
            _FakeCursor({"GEMINI_API_KEY": 0}),
        )
        assert self.VALUE not in log

    def test_explicit_secret_write_is_redacted(self, pbrest, client):
        log = _post_config(
            pbrest, client,
            {"cfgkey": "NEW_KEY", "cfgval": self.VALUE, "secret": True},
            _FakeCursor({}),
        )
        assert self.VALUE not in log

    def test_ordinary_key_value_is_still_logged(self, pbrest, client):
        log = _post_config(
            pbrest, client,
            {"cfgkey": "LOGLEVEL", "cfgval": "4"},
            _FakeCursor({"LOGLEVEL": 0}),
        )
        assert "val 4" in log

    def test_pre_migration_database_uses_heuristic(self, pbrest, client):
        cursor = _FakeCursor({}, missing_column=True)
        with patch.object(pbrest.MySQLdb, "OperationalError", _OperationalError):
            log = _post_config(
                pbrest, client, {"cfgkey": "SOME_TOKEN", "cfgval": self.VALUE}, cursor
            )
            assert self.VALUE not in log
            log = _post_config(
                pbrest, client, {"cfgkey": "LOGLEVEL", "cfgval": "4"}, cursor
            )
            assert "val 4" in log


class TestGetPuzzleNotFound:
    def test_missing_puzzle_is_404(self, pbrest, client):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        with patch.object(pbrest, "_read_cursor", lambda: (MagicMock(), cursor)):
            resp = client.get("/puzzles/999999")
        assert resp.status_code == 404
        body = resp.get_json()
        assert body["status"] == "error"
        assert "999999" in body["error"]


class TestGoogleHttpTimeout:
    def test_thread_http_client_has_timeout(self, pbrest):
        import pbgooglelib

        http_cls = MagicMock()
        with patch.object(pbgooglelib, "httplib2", MagicMock(Http=http_cls)), \
             patch.object(pbgooglelib, "google_auth_httplib2", MagicMock()), \
             patch.object(pbgooglelib, "creds", MagicMock()), \
             patch.object(pbgooglelib, "_thread_local", threading.local()):
            pbgooglelib._get_thread_http()
        http_cls.assert_called_once()
        timeout = http_cls.call_args.kwargs.get("timeout")
        assert timeout is not None and 0 < timeout <= 120
