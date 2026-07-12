"""Tests for config secret redaction and internal-token auth (pblib).

GET /config and GET /huntinfo redact secret values unless the caller
presents the shared internal token. These tests pin down:
- which key names count as secret (patterns + explicit list)
- that redaction preserves response shape (all keys present)
- that empty values pass through (unset secrets show as unset)
- token validation fail-closed behavior and env-over-yaml precedence
"""

import pytest

import pblib
from pblib import (
    REDACTED_SENTINEL,
    is_secret_config_key,
    is_secret_config_entry,
    secret_config_keys,
    redact_config,
    get_internal_token,
    internal_token_valid,
)


class TestIsSecretConfigKey:
    @pytest.mark.parametrize(
        "key",
        [
            "SERVICE_ACCOUNT_JSON",  # explicit — no pattern catches it
            "GEMINI_API_KEY",
            "RECAPTCHA_SECRET_KEY",
            "ACCT_PASSWORD",
            "DISCORD_EMAIL_WEBHOOK",
            "SLACK_EMAIL_WEBHOOK",
            "SOME_FUTURE_TOKEN",
            "somelowercase_api_key",  # case-insensitive
        ],
    )
    def test_secret_keys(self, key):
        assert is_secret_config_key(key) is True

    @pytest.mark.parametrize(
        "key",
        [
            "RECAPTCHA_SITE_KEY",  # public by design — must NOT be redacted
            "DOMAINNAME",
            "LOGLEVEL",
            "BIN_URI",
            "METRICS_METADATA",
            "SERVICE_ACCOUNT_FILE",  # a path, not a secret
            "SERVICE_ACCOUNT_SUBJECT",  # an email, not a secret
            "TEAMNAME",
            "bookmarklet_js",
        ],
    )
    def test_non_secret_keys(self, key):
        assert is_secret_config_key(key) is False


class TestFlagAuthority:
    """The config.secret flag is the authority; the name heuristic is the
    fallback. A key is secret if EITHER says so."""

    def test_flag_only_key_is_secret(self):
        # Innocuous name, explicitly flagged → secret
        assert is_secret_config_entry("SHEETS_ADDON_COOKIES", flagged={"SHEETS_ADDON_COOKIES"}) is True

    def test_heuristic_only_key_is_secret(self):
        # Name matches pattern, not flagged → still secret (fallback fails closed)
        assert is_secret_config_entry("GEMINI_API_KEY", flagged=set()) is True

    def test_neither_flag_nor_heuristic(self):
        assert is_secret_config_entry("DOMAINNAME", flagged=set()) is False

    def test_flagged_none_falls_back_to_heuristic(self):
        # Pre-migration DBs pass flagged=None — heuristic still applies
        assert is_secret_config_entry("ACCT_PASSWORD", flagged=None) is True
        assert is_secret_config_entry("DOMAINNAME", flagged=None) is False

    def test_unflagging_a_pattern_key_does_not_unredact(self):
        # Flag can only ADD secrecy, never remove what the name enforces
        assert is_secret_config_entry("GEMINI_API_KEY", flagged={"OTHER_KEY"}) is True

    def test_redact_config_honors_flag(self):
        cfg = {"INNOCUOUS_NAME": "sensitive-value", "DOMAINNAME": "example.com"}
        redacted = redact_config(cfg, flagged={"INNOCUOUS_NAME"})
        assert redacted["INNOCUOUS_NAME"] == REDACTED_SENTINEL
        assert redacted["DOMAINNAME"] == "example.com"

    def test_secret_config_keys_combines_and_sorts(self):
        cfg = {
            "ZZ_FLAGGED": "x",        # flag only
            "AA_API_KEY": "x",        # heuristic only
            "DOMAINNAME": "x",        # neither
        }
        assert secret_config_keys(cfg, flagged={"ZZ_FLAGGED"}) == ["AA_API_KEY", "ZZ_FLAGGED"]

    def test_secret_config_keys_includes_empty_valued_secrets(self):
        # Classification is by key, not value — an unset secret is still
        # listed so the UI masks it the moment a value is saved
        assert secret_config_keys({"GEMINI_API_KEY": ""}, flagged=set()) == ["GEMINI_API_KEY"]


class TestRedactConfig:
    def test_shape_preserved_and_secrets_masked(self):
        cfg = {
            "DOMAINNAME": "example.com",
            "GEMINI_API_KEY": "sk-abc123",
            "SERVICE_ACCOUNT_JSON": '{"private_key": "..."}',
            "LOGLEVEL": "3",
        }
        redacted = redact_config(cfg)

        # Every key survives — consumers doing config["KEY"] must not break
        assert set(redacted.keys()) == set(cfg.keys())
        assert redacted["DOMAINNAME"] == "example.com"
        assert redacted["LOGLEVEL"] == "3"
        assert redacted["GEMINI_API_KEY"] == REDACTED_SENTINEL
        assert redacted["SERVICE_ACCOUNT_JSON"] == REDACTED_SENTINEL

    def test_empty_secret_values_pass_through(self):
        # An unset secret shows as unset, not as a phantom value
        assert redact_config({"GEMINI_API_KEY": ""}) == {"GEMINI_API_KEY": ""}

    def test_original_dict_not_mutated(self):
        cfg = {"ACCT_PASSWORD": "hunter2"}
        redact_config(cfg)
        assert cfg["ACCT_PASSWORD"] == "hunter2"


class TestInternalToken:
    @pytest.fixture(autouse=True)
    def clean_env(self, monkeypatch):
        monkeypatch.delenv("INTERNAL_TOKEN", raising=False)
        # pblib.config is the parsed puzzleboss.yaml; isolate per test
        original = pblib.config
        yield monkeypatch
        pblib.config = original

    def test_fail_closed_when_unconfigured(self, monkeypatch):
        monkeypatch.setattr(pblib, "config", {"API": {}})
        assert get_internal_token() is None
        assert internal_token_valid("anything") is False
        assert internal_token_valid("") is False
        assert internal_token_valid(None) is False

    def test_yaml_token(self, monkeypatch):
        monkeypatch.setattr(pblib, "config", {"API": {"INTERNAL_TOKEN": "yamltok"}})
        assert get_internal_token() == "yamltok"
        assert internal_token_valid("yamltok") is True
        assert internal_token_valid("wrong") is False

    def test_env_beats_yaml(self, monkeypatch):
        monkeypatch.setenv("INTERNAL_TOKEN", "envtok")
        monkeypatch.setattr(pblib, "config", {"API": {"INTERNAL_TOKEN": "yamltok"}})
        assert get_internal_token() == "envtok"
        assert internal_token_valid("envtok") is True
        assert internal_token_valid("yamltok") is False

    def test_empty_provided_token_never_valid(self, monkeypatch):
        monkeypatch.setattr(pblib, "config", {"API": {"INTERNAL_TOKEN": "tok"}})
        assert internal_token_valid("") is False
        assert internal_token_valid(None) is False

    def test_config_without_api_section(self, monkeypatch):
        monkeypatch.setattr(pblib, "config", {"MYSQL": {}})
        assert get_internal_token() is None
        assert internal_token_valid("x") is False

    def test_config_none(self, monkeypatch):
        monkeypatch.setattr(pblib, "config", None)
        assert get_internal_token() is None
        assert internal_token_valid("x") is False
