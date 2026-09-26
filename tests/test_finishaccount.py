#!/usr/bin/env python3
"""GET /finishaccount step 2: the one-time-password state machine, end to end
through Flask, with the database and Google mocked.

provision_new_google_user's create/reissue/leave-alone decision is covered in
test_account_provisioning. This covers what wraps it: the per-code cooldown
claim, releasing the claim when provisioning fails, and what reaches the
browser (temp_password, reissued, cooldown, email_error).

Run with: pytest tests/test_finishaccount.py -v
"""

import datetime
from unittest.mock import MagicMock, patch

import pytest

CODE = "abcd1234"


def _executed(cursor):
    return " ".join(str(c.args[0]) for c in cursor.execute.call_args_list)


@pytest.fixture
def db(pbrest):
    """A newuser row for CODE, created just now; rowcount 1 = cooldown claim wins."""
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "username": "newsolver", "fullname": "New Solver",
        "email": "new@example.org", "created_at": datetime.datetime.now(),
    }
    cursor.rowcount = 1
    conn = MagicMock()
    with patch.object(pbrest, "_cursor", lambda: (conn, cursor)), \
         patch.object(pbrest, "_solver_exists", lambda _u: True), \
         patch.object(pbrest, "debug_log", lambda *_a, **_k: None), \
         patch.dict(pbrest.configstruct, {"SKIP_GOOGLE_API": "false"}):
        yield cursor


def _step2(pbrest, client, provision, email="OK", step="2"):
    with patch.object(pbrest, "provision_new_google_user", MagicMock(return_value=provision)) as prov, \
         patch.object(pbrest, "email_temp_password", MagicMock(return_value=email)) as mail:
        url = f"/finishaccount/{CODE}" + (f"?step={step}" if step else "")
        resp = client.get(url)
    return resp, prov, mail


def test_created_returns_password_once(pbrest, client, db):
    resp, prov, mail = _step2(pbrest, client, ("created", "pw-one", "OK"))
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["temp_password"] == "pw-one"
    assert body["reissued"] is False and body["cooldown"] is False
    assert "email_error" not in body
    mail.assert_called_once()
    assert mail.call_args.kwargs.get("reissued") is False


def test_reissued_is_flagged_for_the_browser_and_the_email(pbrest, client, db):
    resp, _, mail = _step2(pbrest, client, ("reissued", "pw-two", "OK"))
    body = resp.get_json()
    assert body["reissued"] is True and body["temp_password"] == "pw-two"
    assert mail.call_args.kwargs.get("reissued") is True


def test_cooldown_skips_google_and_email(pbrest, client, db):
    db.rowcount = 0  # someone provisioned this code within the last 10 minutes
    resp, prov, mail = _step2(pbrest, client, ("created", "never", "OK"))
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["cooldown"] is True
    assert "temp_password" not in body
    prov.assert_not_called()
    mail.assert_not_called()


def test_email_failure_is_reported_and_password_still_returned(pbrest, client, db):
    resp, _, _ = _step2(pbrest, client, ("created", "pw-three", "OK"), email="relay down")
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["email_error"] == "relay down"
    assert body["temp_password"] == "pw-three", "browser copy is now the only copy; it must be returned"


def test_already_active_account_is_left_alone(pbrest, client, db):
    resp, _, mail = _step2(pbrest, client, ("already_active", None, "OK"))
    body = resp.get_json()
    assert resp.status_code == 200
    assert "temp_password" not in body
    assert "already set up" in body["message"]
    mail.assert_not_called()


def test_provisioning_error_releases_the_cooldown_claim(pbrest, client, db):
    resp, _, mail = _step2(pbrest, client, ("error", None, "Google said no"))
    assert resp.status_code == 500
    assert "Google said no" in resp.get_json()["error"]
    mail.assert_not_called()
    assert "provisioned_at = NULL" in _executed(db), "a failed attempt must not burn the 10-minute cooldown"


def test_expired_code_is_deleted_and_rejected(pbrest, client, db):
    db.fetchone.return_value["created_at"] = datetime.datetime.now() - datetime.timedelta(hours=49)
    resp, prov, _ = _step2(pbrest, client, ("created", "pw", "OK"))
    assert resp.status_code == 500
    assert "expired" in resp.get_json()["error"].lower()
    assert "DELETE FROM newuser" in _executed(db)
    prov.assert_not_called()


def test_unknown_code_is_rejected(pbrest, client, db):
    db.fetchone.return_value = None
    resp, prov, _ = _step2(pbrest, client, ("created", "pw", "OK"))
    assert resp.status_code == 500
    assert "not valid" in resp.get_json()["error"]
    prov.assert_not_called()


def test_legacy_all_at_once_path_fails_loudly_when_email_fails(pbrest, client, db):
    """With no step the browser never sees temp_password, so a mail failure
    would strand the password with nobody; that must surface as an error."""
    resp, _, _ = _step2(pbrest, client, ("created", "pw", "OK"), email="relay down", step=None)
    assert resp.status_code == 500
    assert "email failed" in resp.get_json()["error"]
