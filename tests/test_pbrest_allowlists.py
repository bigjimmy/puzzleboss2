#!/usr/bin/env python3
"""The SQL-identifier allowlists in pbrest reject unknown parts before any SQL.

pblib's PUZZLE_UPDATABLE_COLUMNS had a test; the four in pbrest did not.
These are the only thing between a URL path segment and a SQL identifier.

Run with: pytest tests/test_pbrest_allowlists.py -v
"""

import os
import re
from unittest.mock import MagicMock, patch

import pytest

BAD_PARTS = ["id; DROP TABLE puzzle", "password", "__proto__", "nope", "1=1"]


def _never_interpolated(db, part):
    """Some handlers legitimately run a lookup (by id, parameterised) before
    the allowlist check. The invariant is that the bad part never reaches
    SQL text, not that no SQL runs at all."""
    cur = db.connection.cursor.return_value
    for call in cur.execute.call_args_list:
        assert part not in str(call.args[0]), f"{part!r} was interpolated into SQL"
SQL = open(os.path.join(os.path.dirname(__file__), "..", "scripts", "puzzleboss.sql")).read()


def _table_columns(table):
    block = re.search(r"CREATE TABLE `%s` \((.*?)\n\) ENGINE" % table, SQL, re.S).group(1)
    return {m.group(1) for m in re.finditer(r"^\s+`(\w+)`", block, re.M)}


def _puzzle_view_columns():
    view = re.search(r"CREATE VIEW puzzle_view AS(.*?);", SQL, re.S).group(1)
    cols = set(re.findall(r"\bp\.(\w+)", view))
    cols |= set(re.findall(r"\)\s+AS\s+(\w+)", view))
    cols |= set(re.findall(r"\bAS\s+(\w+)\s*,", view))
    return cols


@pytest.mark.parametrize("part", BAD_PARTS)
def test_puzzle_view_part_rejected(pbrest, client, part):
    with patch.object(pbrest, "mysql", MagicMock()) as db:
        resp = client.get(f"/puzzles/1/{part}")
    assert resp.status_code == 400
    _never_interpolated(db, part)


@pytest.mark.parametrize("part", BAD_PARTS)
def test_solver_part_rejected(pbrest, client, part):
    with patch.object(pbrest, "mysql", MagicMock()) as db:
        resp = client.post(f"/solvers/1/{part}", json={part: "x"})
    assert resp.status_code == 400
    _never_interpolated(db, part)


@pytest.mark.parametrize("part", BAD_PARTS)
def test_round_part_rejected(pbrest, client, part):
    with patch.object(pbrest, "mysql", MagicMock()) as db:
        resp = client.post(f"/rounds/1/{part}", json={part: "x"})
    assert resp.status_code == 400
    _never_interpolated(db, part)


@pytest.mark.parametrize("priv", BAD_PARTS)
def test_rbac_priv_rejected(pbrest, client, priv):
    with patch.object(pbrest, "internal_token_valid", lambda _t: True), \
         patch.object(pbrest, "mysql", MagicMock()) as db:
        resp = client.post(f"/rbac/{priv}/1", json={"val": "YES"})
    assert resp.status_code == 400
    _never_interpolated(db, priv)


class TestAllowlistsTrackSchema:
    """An allowlist entry that is not a real column is a latent 500; a real
    column missing from the list is a feature nobody can use."""

    def test_puzzle_view_columns_exist(self, pbrest):
        assert pbrest.PUZZLE_VIEW_COLUMNS <= _puzzle_view_columns(), \
            pbrest.PUZZLE_VIEW_COLUMNS - _puzzle_view_columns()

    def test_round_updatable_are_round_columns(self, pbrest):
        cols = _table_columns("round")
        assert pbrest.ROUND_UPDATABLE_COLUMNS <= cols, pbrest.ROUND_UPDATABLE_COLUMNS - cols
        assert "id" not in pbrest.ROUND_UPDATABLE_COLUMNS

    def test_solver_updatable_are_solver_columns(self, pbrest):
        cols = _table_columns("solver")
        assert pbrest.SOLVER_UPDATABLE_COLUMNS <= cols, pbrest.SOLVER_UPDATABLE_COLUMNS - cols
        assert "id" not in pbrest.SOLVER_UPDATABLE_COLUMNS

    def test_priv_columns_are_privs_columns(self, pbrest):
        cols = _table_columns("privs")
        assert pbrest.PRIV_COLUMNS <= cols, pbrest.PRIV_COLUMNS - cols
        assert "uid" not in pbrest.PRIV_COLUMNS
