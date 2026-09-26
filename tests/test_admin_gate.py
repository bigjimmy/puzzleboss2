#!/usr/bin/env python3
"""Every @admin_token_gated route actually enforces the gate.

Only /backups had a test for this. Removing the decorator from any other
gated route would have passed CI, because the Docker suite runs with
ADMIN_TOKEN_ENFORCE off and never sends a token.

Run with: pytest tests/test_admin_gate.py -v
"""

import os
import re
from unittest.mock import MagicMock, patch

import pytest

# (method, concrete path) for every gated route. test_gated_set_is_complete
# fails if pbrest gains or loses a gated route without this list following.
GATED = [
    ("post", "/config"),
    ("post", "/rbac/puzztech/1"),
    ("get", "/deleteuser/someone"),
    ("get", "/newusers"),
    ("delete", "/newusers/1"),
    ("get", "/google/users"),
    ("delete", "/deletepuzzle/SomePuzzle"),
    ("get", "/backups"),
    ("get", "/backups/20260101_000000/activity.csv"),
    ("post", "/migrate/does_not_exist"),
]

EXPECTED_TEMPLATES = {
    ("POST", "/config"), ("POST", "/rbac/<priv>/<uid>"),
    ("GET", "/deleteuser/<username>"), ("GET", "/newusers"),
    ("DELETE", "/newusers/<int:new_user_id>"), ("GET", "/google/users"),
    ("DELETE", "/deletepuzzle/<puzzlename>"), ("GET", "/backups"),
    ("GET", "/backups/<timestamp>/<filename>"), ("POST", "/migrate/<name>"),
}


def _db():
    """A mocked MySQL whose cursors return JSON-serialisable nothing, so a
    handler that runs to completion can still build a response."""
    db = MagicMock()
    cur = db.connection.cursor.return_value
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    cur.rowcount = 0
    return db


def _call(client, method, path):
    fn = getattr(client, method)
    if method == "post":
        return fn(path, json={})
    return fn(path)


def test_gated_set_is_complete():
    """Scan the source for @admin_token_gated and compare to EXPECTED."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "pbrest.py")).read()
    found = set()
    lines = src.split("\n")
    for i, line in enumerate(lines):
        if line.strip() != "@admin_token_gated":
            continue
        for back in range(1, 5):
            m = re.match(r'@app\.route\("([^"]+)".*methods=\[([^\]]+)\]', lines[i - back].strip())
            if m:
                for meth in re.findall(r'"(\w+)"', m.group(2)):
                    found.add((meth, m.group(1)))
                break
    assert found == EXPECTED_TEMPLATES, (
        "gated routes changed; update GATED/EXPECTED_TEMPLATES here and the list in CLAUDE.md"
    )


@pytest.mark.parametrize("method,path", GATED)
def test_enforced_rejects_without_touching_db(pbrest, client, method, path):
    with patch.dict(pbrest.configstruct, {"ADMIN_TOKEN_ENFORCE": "true"}), \
         patch.object(pbrest, "internal_token_valid", lambda _t: False), \
         patch.object(pbrest, "mysql", MagicMock()) as db:
        resp = _call(client, method, path)
    assert resp.status_code == 403
    assert resp.get_json() == {"error": "internal token required"}
    assert db.connection.cursor.call_count == 0, "handler ran before the gate"


@pytest.mark.parametrize("method,path", GATED)
def test_warn_only_mode_lets_request_through_and_logs(pbrest, client, method, path):
    logged = []
    with patch.dict(pbrest.configstruct, {"ADMIN_TOKEN_ENFORCE": "false"}), \
         patch.object(pbrest, "internal_token_valid", lambda _t: False), \
         patch.object(pbrest, "debug_log", lambda sev, msg: logged.append((sev, msg))), \
         patch.object(pbrest, "mysql", _db()):
        resp = _call(client, method, path)
    assert resp.status_code != 403
    assert any(sev == 2 and "allowed without token" in msg for sev, msg in logged), \
        "warn-only mode must leave a SEV2 trail"


@pytest.mark.parametrize("method,path", GATED)
def test_valid_token_passes_gate(pbrest, client, method, path):
    with patch.dict(pbrest.configstruct, {"ADMIN_TOKEN_ENFORCE": "true"}), \
         patch.object(pbrest, "internal_token_valid", lambda _t: True), \
         patch.object(pbrest, "mysql", _db()):
        resp = _call(client, method, path)
    assert resp.status_code != 403
