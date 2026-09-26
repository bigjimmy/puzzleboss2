#!/usr/bin/env python3
"""pbmail_inbox.py reads its config the way pblib does.

Same yaml keys (API.APIURI, API.INTERNAL_TOKEN), same precedence (the
INTERNAL_TOKEN environment variable wins), and the token actually reaches
the request, which is the thing that was silently wrong in production.

Run with: pytest tests/test_pbmail_config.py -v
"""

import importlib.util
import os
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="module")
def pbmail():
    added = []
    if "requests" not in sys.modules:
        try:
            importlib.import_module("requests")
        except ImportError:
            sys.modules["requests"] = MagicMock()
            added.append("requests")
    path = os.path.join(os.path.dirname(__file__), "..", "scripts", "pbmail_inbox.py")
    spec = importlib.util.spec_from_file_location("pbmail_inbox", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    yield mod
    for name in added:
        sys.modules.pop(name, None)


@pytest.fixture
def yaml_file(tmp_path):
    p = tmp_path / "puzzleboss.yaml"
    p.write_text("API:\n  APIURI: http://api.test:5000\n  INTERNAL_TOKEN: file-token\n")
    return str(p)


def _ok_response(config):
    resp = MagicMock()
    resp.json.return_value = {"status": "ok", "config": config}
    return resp


def test_reads_pblib_keys_and_sends_the_token(pbmail, yaml_file, monkeypatch):
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    with patch.object(pbmail.requests, "get", return_value=_ok_response({"DISCORD_EMAIL_WEBHOOK": "https://d"})) as get:
        cfg = pbmail.load_config(yaml_file)
    assert cfg["DISCORD_EMAIL_WEBHOOK"] == "https://d"
    assert get.call_args.args[0] == "http://api.test:5000/config"
    assert get.call_args.kwargs["headers"]["X-PB-Internal-Token"] == "file-token"


def test_environment_token_wins_like_pblib(pbmail, yaml_file, monkeypatch):
    monkeypatch.setenv("INTERNAL_TOKEN", "env-token")
    with patch.object(pbmail.requests, "get", return_value=_ok_response({})) as get:
        pbmail.load_config(yaml_file)
    assert get.call_args.kwargs["headers"]["X-PB-Internal-Token"] == "env-token"


def test_missing_token_warns_and_sends_none(pbmail, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    p = tmp_path / "puzzleboss.yaml"
    p.write_text("API:\n  APIURI: http://api.test:5000\n")
    with patch.object(pbmail.requests, "get", return_value=_ok_response({})) as get:
        pbmail.load_config(str(p))
    assert "X-PB-Internal-Token" not in get.call_args.kwargs["headers"]
    assert "INTERNAL_TOKEN" in capsys.readouterr().err


def test_missing_apiuri_is_an_error_not_a_default(pbmail, tmp_path, monkeypatch):
    """The old code silently defaulted to localhost, which is wrong on the
    mail host. Like pblib, a broken yaml is an error."""
    p = tmp_path / "puzzleboss.yaml"
    p.write_text("API_URI: http://legacy-key\n")
    with patch.object(pbmail.requests, "get") as get:
        assert pbmail.load_config(str(p)) is None
    get.assert_not_called()


def test_check_config_reports_redaction(pbmail, yaml_file, monkeypatch, capsys):
    monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
    with patch.object(pbmail.requests, "get", return_value=_ok_response({
        "DISCORD_EMAIL_WEBHOOK": "********", "SLACK_EMAIL_WEBHOOK": "",
    })):
        assert pbmail.check_config(yaml_file) == 1
    out = capsys.readouterr().out
    assert "REDACTED" in out and "not set" in out


def test_check_config_passes_with_one_usable_webhook(pbmail, yaml_file, monkeypatch):
    with patch.object(pbmail.requests, "get", return_value=_ok_response({
        "DISCORD_EMAIL_WEBHOOK": "", "SLACK_EMAIL_WEBHOOK": "https://hooks.slack/x",
    })):
        assert pbmail.check_config(yaml_file) == 0
