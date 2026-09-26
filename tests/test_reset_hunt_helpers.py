#!/usr/bin/env python3
"""Pure helpers in scripts/reset-hunt.py.

The mysql batch-output unescaper shipped with a wrong assumption about NULL
and was hot-fixed the same day; this pins the verified behaviour.

Run with: pytest tests/test_reset_hunt_helpers.py -v
"""

import importlib.util
import os
import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(scope="module")
def rh():
    added = []
    for name in ("requests",):  # CI's unit runner does not install it
        try:
            importlib.import_module(name)
        except ImportError:
            sys.modules[name] = MagicMock()
            added.append(name)
    path = os.path.join(os.path.dirname(__file__), "..", "scripts", "reset-hunt.py")
    spec = importlib.util.spec_from_file_location("reset_hunt", path)
    mod = importlib.util.module_from_spec(spec)
    saved_argv = sys.argv
    sys.argv = ["reset-hunt.py"]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved_argv
    yield mod
    for name in added:
        sys.modules.pop(name, None)


@pytest.mark.parametrize("raw,expected", [
    ("plain", "plain"),
    ("a\\tb", "a\tb"),
    ("line1\\nline2", "line1\nline2"),
    ("cr\\rlf", "cr\rlf"),
    ("back\\\\slash", "back\\slash"),
    ("nul\\0byte", "nul\0byte"),
    ("NULL", "NULL"),          # the client prints NULL as text; it is not unescaped
    (r"\\N", r"\N"),           # a literal backslash-N in data arrives escaped
    ("", ""),
])
def test_unescape_mysql(rh, raw, expected):
    assert rh._unescape_mysql(raw) == expected


def test_redact_masks_only_the_password_argument(rh):
    cmd = ["mysqldump", "-h", "host", "-u", "user", "-phunter2", "--routines", "puzzleboss2"]
    assert rh._redact(cmd) == ["mysqldump", "-h", "host", "-u", "user", "-p<redacted>", "--routines", "puzzleboss2"]
    assert "hunter2" not in " ".join(rh._redact(cmd))


def test_redact_does_not_mangle_the_original(rh):
    cmd = ["mysql", "-psecret"]
    rh._redact(cmd)
    assert cmd == ["mysql", "-psecret"]


def test_s3_backup_bucket_matches_terraform(rh):
    infra = os.path.join(os.path.dirname(__file__), "..", "..", "puzzleboss2-infra", "terraform", "s3.tf")
    if not os.path.exists(infra):
        pytest.skip("infra repo not checked out beside the app repo")
    assert f'bucket = "${{var.project_name}}-hunt-backups"' in open(infra).read()
    assert rh.S3_BACKUP_BUCKET == "puzzleboss-hunt-backups"
