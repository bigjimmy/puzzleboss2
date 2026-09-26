#!/usr/bin/env python3
"""Tests for the hunt CSV archive endpoints.

The property worth pinning down is the allowlist. The same S3 prefix holds
full database dumps whose config table contains SERVICE_ACCOUNT_JSON — the
Google Workspace service account key with Domain-Wide Delegation. Those must
be unreachable from the web tier. There are three gates (the ECS task role is
scoped to *.csv.gz, the API allowlists two filenames, the PHP page allowlists
the same two); this covers the API one, which is the only one testable here.

Run with: pytest tests/test_backup_archives.py -v
"""

import datetime
import gzip
import importlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# Importing pbrest pulls in flask_mysqldb and, through pbgooglelib, the whole
# Google client stack. CI installs neither. Stub anything absent BEFORE the
# import rather than relying on another test file having done it: collection
# order is alphabetical today, so test_account_provisioning happens to stub
# the Google modules first, and this file would silently start failing if that
# file were renamed or run separately.
_GOOGLE_STACK = (
    "googleapiclient",
    "googleapiclient.discovery",
    "googleapiclient.errors",
    "google.auth",
    "google.auth.transport",
    "google.auth.transport.requests",
    "google.oauth2",
    "google.oauth2.service_account",
    "google_auth_httplib2",
    "httplib2",
)


@pytest.fixture(scope="module")
def pbrest():
    """Import pbrest with everything it needs but CI does not install."""
    if "flask_mysqldb" not in sys.modules:
        fake = types.ModuleType("flask_mysqldb")

        class _MySQL:
            def __init__(self, app=None):
                self.connection = MagicMock()

        fake.MySQL = _MySQL
        sys.modules["flask_mysqldb"] = fake

    for name in _GOOGLE_STACK:
        if name not in sys.modules:
            try:
                importlib.import_module(name)
            except ImportError:
                sys.modules[name] = MagicMock()

    import pbrest as _pbrest

    return _pbrest


@pytest.fixture
def client(pbrest):
    pbrest.app.config["TESTING"] = True
    # before_request refreshes config off the DB; it is irrelevant here.
    with patch.object(pbrest, "maybe_refresh_config", lambda: None):
        with pbrest.app.test_client() as c:
            yield c


@pytest.fixture
def open_gate(pbrest):
    """Treat the internal token as valid, so these tests exercise the
    allowlist rather than re-testing admin_token_gated."""
    with patch.object(pbrest, "internal_token_valid", lambda _t: True):
        yield


def _s3_listing(keys_and_sizes):
    client = MagicMock()
    page = {
        "Contents": [
            {
                "Key": k,
                "Size": n,
                "LastModified": datetime.datetime(2026, 2, 15, 3, 15, 0),
            }
            for k, n in keys_and_sizes
        ]
    }
    client.get_paginator.return_value.paginate.return_value = [page]
    return client


class TestListBackups:
    def test_lists_only_the_two_csvs(self, pbrest, client, open_gate):
        s3 = _s3_listing([
            ("db/20260215_031500/activity.csv.gz", 253126),
            ("db/20260215_031500/puzzle_view.csv.gz", 35230),
            # All of these must be filtered out.
            ("db/20260215_031500/full_database_backup.sql.gz", 279038),
            ("db/20260215_031500/config.sql.gz", 12596),
            ("db/20260215_031500/solver.sql.gz", 9092),
        ])
        with patch.object(pbrest, "_s3_client", lambda: s3):
            resp = client.get("/backups")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "ok"
        assert len(body["backups"]) == 1
        names = [f["name"] for f in body["backups"][0]["files"]]
        assert names == ["activity.csv", "puzzle_view.csv"]

    def test_newest_set_first(self, pbrest, client, open_gate):
        s3 = _s3_listing([
            ("db/20250101_000000/activity.csv.gz", 1),
            ("db/20260215_031500/activity.csv.gz", 1),
            ("db/20250615_120000/activity.csv.gz", 1),
        ])
        with patch.object(pbrest, "_s3_client", lambda: s3):
            body = client.get("/backups").get_json()

        assert [b["timestamp"] for b in body["backups"]] == [
            "20260215_031500", "20250615_120000", "20250101_000000",
        ]

    def test_unexpected_csv_name_is_not_listed(self, pbrest, client, open_gate):
        """Only the two known exports; a stray CSV is not advertised."""
        s3 = _s3_listing([("db/20260215_031500/solver_emails.csv.gz", 999)])
        with patch.object(pbrest, "_s3_client", lambda: s3):
            body = client.get("/backups").get_json()

        assert body["backups"] == []

    def test_s3_failure_is_reported_not_raised(self, pbrest, client, open_gate):
        s3 = MagicMock()
        s3.get_paginator.side_effect = RuntimeError("no credentials")
        with patch.object(pbrest, "_s3_client", lambda: s3):
            resp = client.get("/backups")

        assert resp.status_code == 500
        assert resp.get_json()["status"] == "error"


class TestDownloadBackup:
    def test_serves_a_decompressed_csv(self, pbrest, client, open_gate):
        csv_bytes = b"id,name\n1,Watchtower\n"
        s3 = MagicMock()
        s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: gzip.compress(csv_bytes))
        }
        with patch.object(pbrest, "_s3_client", lambda: s3):
            resp = client.get("/backups/20260215_031500/activity.csv")

        assert resp.status_code == 200
        assert resp.data == csv_bytes
        assert resp.mimetype == "text/csv"
        assert "attachment" in resp.headers["Content-Disposition"]
        assert s3.get_object.call_args.kwargs["Key"] == (
            "db/20260215_031500/activity.csv.gz"
        )

    @pytest.mark.parametrize("filename", [
        "full_database_backup.sql",
        "full_database_backup.sql.gz",
        "config.sql",
        "solver.sql",
    ])
    def test_sql_dumps_are_never_served(self, pbrest, client, open_gate, filename):
        """The whole point: these carry SERVICE_ACCOUNT_JSON."""
        s3 = MagicMock()
        with patch.object(pbrest, "_s3_client", lambda: s3):
            resp = client.get(f"/backups/20260215_031500/{filename}")

        assert resp.status_code == 404
        s3.get_object.assert_not_called()

    @pytest.mark.parametrize("timestamp", [
        "../../etc", "20260215 031500", "ts/with/slashes", "a" * 65,
    ])
    def test_malformed_timestamps_rejected(self, pbrest, client, open_gate, timestamp):
        s3 = MagicMock()
        with patch.object(pbrest, "_s3_client", lambda: s3):
            resp = client.get(f"/backups/{timestamp}/activity.csv")

        assert resp.status_code in (400, 404)
        s3.get_object.assert_not_called()

    def test_missing_object_is_404_not_500(self, pbrest, client, open_gate):
        s3 = MagicMock()
        s3.get_object.side_effect = RuntimeError("NoSuchKey")
        with patch.object(pbrest, "_s3_client", lambda: s3):
            resp = client.get("/backups/20260215_031500/puzzle_view.csv")

        assert resp.status_code == 404


class TestGateIsApplied:
    def test_both_endpoints_require_the_internal_token_when_enforcing(self, pbrest, client):
        """admin_token_gated is wired up, and enforcement actually blocks."""
        with patch.dict(pbrest.configstruct, {"ADMIN_TOKEN_ENFORCE": "true"}, clear=False):
            with patch.object(pbrest, "internal_token_valid", lambda _t: False):
                assert client.get("/backups").status_code == 403
                assert client.get(
                    "/backups/20260215_031500/activity.csv"
                ).status_code == 403
