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


class TestPuzzleUpdateNotFound:
    @pytest.mark.parametrize("path,body", [
        ("/puzzles/999999/xyzloc", {"xyzloc": "here"}),
        ("/puzzles/999999", {"xyzloc": "here"}),
    ])
    def test_update_of_missing_puzzle_is_404(self, pbrest, client, path, body):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        with patch.object(pbrest, "_read_cursor", lambda: (MagicMock(), cursor)):
            resp = client.post(path, json=body)
        assert resp.status_code == 404


class _TagCursor:
    """Fake cursor for the tags handler: records SQL and commits in order."""

    def __init__(self, events, existing_tag_id=None, puzzle_tags=None):
        self.events = events
        self.existing_tag_id = existing_tag_id
        self.puzzle_tags = puzzle_tags
        self.lastrowid = 77
        self._row = None

    def execute(self, sql, params=()):
        self.events.append(sql)
        if sql.startswith("SELECT id FROM tag"):
            self._row = {"id": self.existing_tag_id} if self.existing_tag_id else None
        elif sql.startswith("SELECT tags FROM puzzle"):
            self._row = {"tags": self.puzzle_tags}
        else:
            self._row = None

    def fetchone(self):
        return self._row


class TestTagUpdateLocking:
    """Tag edits are a JSON read-modify-write (audit finding H7)."""

    def _add(self, pbrest, client, cursor, events):
        conn = MagicMock()
        conn.commit.side_effect = lambda: events.append("COMMIT")
        with patch.object(pbrest, "_cursor", lambda: (conn, cursor)), \
             patch.object(pbrest, "get_one_puzzle",
                          lambda _id: {"status": "ok", "puzzle": {"id": 5, "name": "P"}}), \
             patch.object(pbrest, "increment_botstat", lambda *a: None), \
             patch.object(pbrest, "invalidate_cache_with_stats", lambda: None), \
             patch.object(pbrest.pblib, "log_activity", lambda *a, **k: True):
            resp = client.post("/puzzles/5/tags", json={"tags": {"add": "newtag"}})
        assert resp.status_code == 200, resp.get_json()

    def test_read_is_locked_and_after_tag_creation_commit(self, pbrest, client):
        events = []
        self._add(pbrest, client, _TagCursor(events, puzzle_tags="[3]"), events)

        read = next(i for i, e in enumerate(events) if e.startswith("SELECT tags FROM puzzle"))
        assert "FOR UPDATE" in events[read]
        create = next(i for i, e in enumerate(events) if e.startswith("INSERT INTO tag"))
        # the tag-creation commit comes before the lock, not between it and the write
        assert "COMMIT" in events[create:read]
        write = next(i for i, e in enumerate(events) if e.startswith("UPDATE puzzle SET tags"))
        assert read < write
        assert "COMMIT" not in events[read:write]
        assert "COMMIT" in events[write:]

    def test_noop_add_still_releases_lock(self, pbrest, client):
        events = []
        self._add(pbrest, client,
                  _TagCursor(events, existing_tag_id=3, puzzle_tags="[3]"), events)
        read = next(i for i, e in enumerate(events) if e.startswith("SELECT tags FROM puzzle"))
        assert not any(e.startswith("UPDATE puzzle SET tags") for e in events)
        assert "COMMIT" in events[read:]


class _HttpError(Exception):
    """Stands in for googleapiclient.errors.HttpError (stubbed in unit tests)."""

    def __init__(self, status, text="error"):
        super().__init__(text)
        self.resp = MagicMock(status=status)


class TestActivityReadErrorClassification:
    """_pb_activity read failures say whether the sheet itself is at fault,
    so bigjimmybot doesn't rebuild tabs during a Google outage."""

    def _read(self, pbrest, exc):
        import pbgooglelib

        values = MagicMock()
        values.get.return_value.execute.side_effect = exc
        sheets = MagicMock()
        sheets.spreadsheets.return_value.values.return_value = values
        with patch.object(pbgooglelib, "sheetsservice", sheets), \
             patch.object(pbgooglelib.googleapiclient.errors, "HttpError", _HttpError), \
             patch.object(pbgooglelib, "_get_thread_http", lambda: None), \
             patch.object(pbgooglelib, "_rate_limiter", MagicMock()), \
             patch.object(pbgooglelib, "debug_log", lambda *a: None), \
             patch.object(pbgooglelib.time, "sleep", lambda s: None), \
             patch.dict(pbgooglelib.configstruct, {
                 "SKIP_GOOGLE_API": "false",
                 "BIGJIMMY_QUOTAFAIL_MAX_RETRIES": "2",
                 "BIGJIMMY_QUOTAFAIL_DELAY": "0",
             }):
            return pbgooglelib.get_puzzle_sheet_info_activity("fileid", "P")

    @pytest.mark.parametrize("exc", [
        _HttpError(500), _HttpError(503), _HttpError(408),
        ConnectionResetError("reset"), TimeoutError("timed out"),
        _HttpError(429, "RATE_LIMIT_EXCEEDED"),  # retries exhausted
    ])
    def test_transient(self, pbrest, exc):
        result = self._read(pbrest, exc)
        assert result["error"] is True
        assert result["error_transient"] is True

    @pytest.mark.parametrize("exc", [_HttpError(400, "bad request"), _HttpError(403), _HttpError(404)])
    def test_sheet_specific(self, pbrest, exc):
        result = self._read(pbrest, exc)
        assert result["error"] is True
        assert result["error_transient"] is False

    def test_missing_tab_is_not_an_error(self, pbrest):
        result = self._read(pbrest, _HttpError(400, "Unable to parse range: _pb_activity!A:C"))
        assert result["error"] is False
