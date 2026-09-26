#!/usr/bin/env python3
"""
Unit tests for the passwordless signup flow:
  - pblib.generate_temp_password (pure)
  - pbgooglelib.provision_new_google_user (Google API mocked)

What this file deliberately does NOT try to cover: the real Google Workspace
API, real SMTP delivery, or the browser JS. Those require live credentials/a
live mail relay/a live task and are exercised by hand against the real stack
(as this feature was before deploying it), not by an automated unit test.
What IS unit-testable, and matters most, is the decision logic around
"create vs. reissue vs. leave alone" -- that's where a bug would either lock
someone out of signing up at all, or (worse) silently overwrite a real
person's already-chosen password. This file pins that logic down.

Run with: pytest tests/test_account_provisioning.py -v
"""

import importlib
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Real pblib first (conftest.py has already stubbed MySQLdb for it), so the
# pure generate_temp_password tests below exercise the actual implementation,
# not a mock.
import pblib  # noqa: E402


class TestGenerateTempPassword(unittest.TestCase):
    """generate_temp_password is the one piece of this feature with no
    external dependency at all -- test it directly, no mocking needed."""

    def test_default_length_is_reasonable(self):
        pw = pblib.generate_temp_password()
        # secrets.token_urlsafe(18) yields ~24 base64url chars; just assert
        # it's comfortably long, not a specific byte count implementation detail.
        self.assertGreaterEqual(len(pw), 20)

    def test_respects_requested_length(self):
        short = pblib.generate_temp_password(length=4)
        long = pblib.generate_temp_password(length=40)
        self.assertLess(len(short), len(long))

    def test_is_url_and_copy_paste_safe(self):
        pw = pblib.generate_temp_password()
        # token_urlsafe's alphabet: A-Za-z0-9-_ . No characters that would be
        # mangled by HTML rendering, email clients, or URL-encoding.
        allowed = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        )
        self.assertTrue(set(pw) <= allowed, f"unexpected characters in {pw!r}")

    def test_not_predictable_across_calls(self):
        passwords = {pblib.generate_temp_password() for _ in range(50)}
        self.assertEqual(len(passwords), 50, "generate_temp_password produced a collision")


# --- pbgooglelib.provision_new_google_user -----------------------------
#
# Mirrors the mocking approach in test_rate_limiter.py: stub the heavy
# google-api-python-client / MySQLdb / pblib modules before importing
# pbgooglelib, then restore sys.modules so the stubs don't leak into other
# test files. googleapiclient.errors.HttpError is given a real minimal
# implementation (not a bare MagicMock) so `except ... HttpError:` in the
# code under test can actually catch instances we raise.


class _FakeHttpError(Exception):
    """Stand-in for googleapiclient.errors.HttpError with just the two
    attributes provision_new_google_user reads: resp.status and content."""

    def __init__(self, status, message):
        self.resp = MagicMock(status=status)
        self.content = json.dumps({"error": {"message": message}}).encode()
        super().__init__(message)


_saved_modules = {
    name: sys.modules.get(name)
    for name in (
        "MySQLdb", "MySQLdb.cursors", "googleapiclient", "googleapiclient.discovery",
        "googleapiclient.errors", "google.auth", "google.auth.transport",
        "google.auth.transport.requests", "google.oauth2", "google.oauth2.service_account",
        "google_auth_httplib2", "httplib2", "pblib",
    )
}

sys.modules["MySQLdb"] = MagicMock()
sys.modules["MySQLdb.cursors"] = MagicMock()
sys.modules["googleapiclient"] = MagicMock()
sys.modules["googleapiclient"].errors.HttpError = _FakeHttpError
sys.modules["googleapiclient.discovery"] = MagicMock()
sys.modules["googleapiclient.errors"] = MagicMock(HttpError=_FakeHttpError)
sys.modules["google.auth"] = MagicMock()
sys.modules["google.auth.transport"] = MagicMock()
sys.modules["google.auth.transport.requests"] = MagicMock()
sys.modules["google.oauth2"] = MagicMock()
sys.modules["google.oauth2.service_account"] = MagicMock()
sys.modules["google_auth_httplib2"] = MagicMock()
sys.modules["httplib2"] = MagicMock()

_pblib_mock = MagicMock()
_pblib_mock.configstruct = {"DOMAINNAME": "importanthuntpoll.org"}
_pblib_mock.debug_log = lambda level, msg: None
sys.modules["pblib"] = _pblib_mock

if "pbgooglelib" in sys.modules and isinstance(sys.modules["pbgooglelib"], MagicMock):
    del sys.modules["pbgooglelib"]

import pbgooglelib  # noqa: E402

importlib.reload(pbgooglelib)
from pbgooglelib import provision_new_google_user  # noqa: E402

for _name, _orig in _saved_modules.items():
    if _orig is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _orig


class TestProvisionNewGoogleUser(unittest.TestCase):
    """The three-way decision (create / reissue / leave alone) is the part
    of this feature where a mistake is either "signup is broken" (annoying)
    or "we silently reset a real person's chosen password" (bad) -- so it's
    the part worth pinning down with tests, independent of live Google
    credentials.
    """

    def setUp(self):
        # Patch pbgooglelib's actual module attributes directly (rather than
        # relying on the collection-time stub-and-reload above) so this test
        # is correct regardless of what any OTHER test file's import-time
        # module surgery does to the shared pbgooglelib module object --
        # e.g. test_rate_limiter.py does the same stub/reload dance for the
        # same module, and whichever file's reload runs later at collection
        # time would otherwise silently win, leaving this file's mocks
        # pointing at stale objects.
        patchers = [
            patch.object(pbgooglelib, "configstruct", {"DOMAINNAME": "importanthuntpoll.org"}),
            patch.object(pbgooglelib, "pblib", MagicMock(
                generate_temp_password=MagicMock(return_value="fixed-temp-pw"),
            )),
            # googleapiclient.errors.HttpError specifically must stay _FakeHttpError
            # (a real exception class) for `except googleapiclient.errors.HttpError`
            # in the code under test to work -- same cross-file-collision risk as
            # configstruct/pblib above.
            patch.object(pbgooglelib, "googleapiclient", MagicMock(
                errors=MagicMock(HttpError=_FakeHttpError),
            )),
            patch.object(pbgooglelib, "_rate_limiter", MagicMock(acquire=lambda: None)),
            patch.object(pbgooglelib, "initadmin", lambda: None),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_created_when_account_is_new(self):
        with patch("pbgooglelib.build") as mock_build:
            userservice = mock_build.return_value
            userservice.users.return_value.insert.return_value.execute.return_value = {}

            status, temp_password, message = provision_new_google_user(
                "newsolver", "New", "Solver"
            )

        self.assertEqual(status, "created")
        self.assertEqual(temp_password, "fixed-temp-pw")
        self.assertEqual(message, "OK")
        userservice.users.return_value.get.assert_not_called()
        userservice.users.return_value.update.assert_not_called()

        insert_body = userservice.users.return_value.insert.call_args.kwargs["body"]
        self.assertEqual(insert_body["password"], "fixed-temp-pw")
        self.assertIs(insert_body["changePasswordAtNextLogin"], True)

    def test_reissued_when_existing_account_never_activated(self):
        with patch("pbgooglelib.build") as mock_build:
            userservice = mock_build.return_value
            userservice.users.return_value.insert.return_value.execute.side_effect = (
                _FakeHttpError(409, "Entity already exists.")
            )
            userservice.users.return_value.get.return_value.execute.return_value = {
                "changePasswordAtNextLogin": True
            }
            # Google's real users().update() returns the updated user resource
            # (non-empty) on success; change_google_user_password treats an
            # empty dict as failure, so the mock must look like a real response.
            userservice.users.return_value.update.return_value.execute.return_value = {
                "primaryEmail": "stalledsolver@importanthuntpoll.org",
                "changePasswordAtNextLogin": True,
            }

            status, temp_password, message = provision_new_google_user(
                "stalledsolver", "Stalled", "Solver"
            )

        self.assertEqual(status, "reissued")
        self.assertEqual(temp_password, "fixed-temp-pw")
        userservice.users.return_value.update.assert_called_once()
        update_body = userservice.users.return_value.update.call_args.kwargs["body"]
        self.assertEqual(update_body["password"], "fixed-temp-pw")
        self.assertIs(update_body["changePasswordAtNextLogin"], True)

    def test_already_active_account_is_never_touched(self):
        """The critical safety property: if the owner already completed their
        forced password change, a retry (e.g. someone re-clicking an old
        email link) must NEVER reset their real password."""
        with patch("pbgooglelib.build") as mock_build:
            userservice = mock_build.return_value
            userservice.users.return_value.insert.return_value.execute.side_effect = (
                _FakeHttpError(409, "Entity already exists.")
            )
            userservice.users.return_value.get.return_value.execute.return_value = {
                "changePasswordAtNextLogin": False
            }

            status, temp_password, message = provision_new_google_user(
                "activesolver", "Active", "Solver"
            )

        self.assertEqual(status, "already_active")
        self.assertIsNone(temp_password)
        userservice.users.return_value.update.assert_not_called()

    def test_insert_error_other_than_conflict_is_reported(self):
        with patch("pbgooglelib.build") as mock_build:
            userservice = mock_build.return_value
            userservice.users.return_value.insert.return_value.execute.side_effect = (
                _FakeHttpError(500, "Internal error")
            )

            status, temp_password, message = provision_new_google_user(
                "erroruser", "Error", "User"
            )

        self.assertEqual(status, "error")
        self.assertIsNone(temp_password)
        self.assertIn("Internal error", message)
        userservice.users.return_value.get.assert_not_called()
        userservice.users.return_value.update.assert_not_called()

    def test_lookup_failure_after_conflict_is_reported(self):
        with patch("pbgooglelib.build") as mock_build:
            userservice = mock_build.return_value
            userservice.users.return_value.insert.return_value.execute.side_effect = (
                _FakeHttpError(409, "Entity already exists.")
            )
            userservice.users.return_value.get.return_value.execute.side_effect = (
                _FakeHttpError(500, "lookup boom")
            )

            status, temp_password, message = provision_new_google_user(
                "lookupfail", "Lookup", "Fail"
            )

        self.assertEqual(status, "error")
        self.assertIsNone(temp_password)
        userservice.users.return_value.update.assert_not_called()


class TestPasswordNeverLogged(unittest.TestCase):
    """Every log line emitted while a one-time password is in flight must
    redact it. LOGLEVEL is operator-tunable at runtime and logs ship to Loki,
    so a trace-level leak is one config flip away from being a real leak."""

    def test_change_google_user_password_redacts_trace_log(self):
        logged = []
        patchers = [
            patch.object(pbgooglelib, "configstruct", {"DOMAINNAME": "importanthuntpoll.org"}),
            patch.object(pbgooglelib, "debug_log", lambda level, msg: logged.append(msg)),
            patch.object(pbgooglelib, "_rate_limiter", MagicMock(acquire=lambda: None)),
            patch.object(pbgooglelib, "initadmin", lambda: None),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        with patch("pbgooglelib.build") as mock_build:
            userservice = mock_build.return_value
            userservice.users.return_value.update.return_value.execute.return_value = {
                "primaryEmail": "x@importanthuntpoll.org"
            }
            result = pbgooglelib.change_google_user_password(
                "x", "s3cret-one-time", change_password_at_next_login=True
            )

        self.assertEqual(result, "OK")
        self.assertTrue(logged, "expected some log output")
        for line in logged:
            self.assertNotIn("s3cret-one-time", line)
        # The request body itself must still carry the password.
        body = userservice.users.return_value.update.call_args.kwargs["body"]
        self.assertEqual(body["password"], "s3cret-one-time")
        self.assertTrue(body["changePasswordAtNextLogin"])


class TestRegistrationEmails(unittest.TestCase):
    """SMTP is mocked; these pin down the copy and the no-logging rule."""

    def setUp(self):
        self.logged = []
        self.sent = []
        smtp = MagicMock()
        smtp.return_value.send_message.side_effect = lambda m: self.sent.append(m)
        patchers = [
            patch.object(pblib, "configstruct", {
                "TEAMNAME": "Mystik Spiral", "DOMAINNAME": "importanthuntpoll.org",
                "REGEMAIL": "reg@importanthuntpoll.org", "MAILRELAY": "relay",
                "ACCT_URI": "https://acct.example",
            }),
            patch.object(pblib, "debug_log", lambda level, msg: self.logged.append(msg)),
            patch.object(pblib.smtplib, "SMTP", smtp),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

    def test_temp_password_email_created_copy(self):
        result = pblib.email_temp_password("a@b.c", "New Solver", "newsolver", "pw-abc")
        self.assertEqual(result, "OK")
        msg = self.sent[0]
        self.assertIn("is ready", msg["Subject"])
        self.assertIn("pw-abc", msg.get_content())
        self.assertNotIn("no longer works", msg.get_content())
        for line in self.logged:
            self.assertNotIn("pw-abc", line)

    def test_temp_password_email_reissued_copy(self):
        pblib.email_temp_password("a@b.c", "New Solver", "newsolver", "pw-xyz", reissued=True)
        msg = self.sent[0]
        self.assertIn("reissued", msg["Subject"])
        self.assertIn("no longer works", msg.get_content())
        self.assertIn("pw-xyz", msg.get_content())

    def test_verification_email_never_logs_code(self):
        result = pblib.email_user_verification("a@b.c", "c0de1234", "New Solver", "newsolver")
        self.assertEqual(result, "OK")
        self.assertIn("c0de1234", self.sent[0].get_content())
        for line in self.logged:
            self.assertNotIn("c0de1234", line)

    def test_click_tracking_disabled(self):
        """SendGrid rewrites every URL into a ct.sendgrid.net redirect unless
        told not to, which mangles the verification link and makes the mail
        look like phishing."""
        pblib.email_user_verification("a@b.c", "c0de1234", "New Solver", "newsolver")
        header = self.sent[0]["X-SMTPAPI"]
        assert json.loads(header)["filters"]["clicktrack"]["settings"]["enable"] == 0

    def test_smtp_failure_returns_error_string(self):
        pblib.smtplib.SMTP.side_effect = OSError("relay down")
        result = pblib.email_temp_password("a@b.c", "New Solver", "newsolver", "pw-abc")
        self.assertEqual(result, "relay down")
        for line in self.logged:
            self.assertNotIn("pw-abc", line)


if __name__ == "__main__":
    unittest.main()
