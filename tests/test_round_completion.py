#!/usr/bin/env python3
"""pblib.check_round_completion — the "round is done" decision.

Only an ID-type test existed, so the actual rule was never asserted: a
round is Solved exactly when it has metas and every one of them is
solved, and a round that stops qualifying is put back to New. Getting
this wrong either hides a finished round from the board or marks a live
round complete mid-hunt.

Run with: pytest tests/test_round_completion.py -v
"""

from unittest.mock import MagicMock, patch

import pytest

import pblib


def _conn(total, solved, unmark_rowcount=1):
    """A connection whose meta-puzzle count query returns (total, solved)."""
    cursor = MagicMock()
    cursor.fetchone.return_value = {"total": total, "solved": solved}
    cursor.rowcount = unmark_rowcount
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


def _statements(cursor):
    return " | ".join(str(c.args[0]) for c in cursor.execute.call_args_list)


@pytest.fixture(autouse=True)
def quiet():
    with patch.object(pblib, "debug_log", lambda *a, **k: None), \
         patch.object(pblib, "_invalidate_cache", MagicMock()) as inv:
        yield inv


def test_all_metas_solved_marks_the_round_solved(quiet):
    conn, cursor = _conn(total=3, solved=3)
    pblib.check_round_completion(7, conn)
    assert "UPDATE round SET status = 'Solved'" in _statements(cursor)
    conn.commit.assert_called_once()
    quiet.assert_called_once_with(conn)


def test_one_meta_outstanding_does_not_mark_solved(quiet):
    conn, cursor = _conn(total=3, solved=2)
    pblib.check_round_completion(7, conn)
    assert "SET status = 'Solved'" not in _statements(cursor)


def test_round_with_no_metas_is_left_alone(quiet):
    """A round nobody has given a meta yet must never auto-complete."""
    conn, cursor = _conn(total=0, solved=None)
    pblib.check_round_completion(7, conn)
    assert "UPDATE round" not in _statements(cursor)
    conn.commit.assert_not_called()
    quiet.assert_not_called()


def test_unsolving_a_meta_puts_the_round_back_to_new(quiet):
    conn, cursor = _conn(total=2, solved=1, unmark_rowcount=1)
    pblib.check_round_completion(7, conn)
    stmts = _statements(cursor)
    assert "UPDATE round SET status = 'New'" in stmts
    assert "status = 'Solved'" in stmts, "the revert must be conditional on it being Solved"
    conn.commit.assert_called_once()
    quiet.assert_called_once_with(conn)


def test_already_unsolved_round_does_not_churn_the_cache(quiet):
    """The revert UPDATE matches nothing, so nothing changed: no commit, no
    invalidation. This is the common case on every non-final meta solve."""
    conn, cursor = _conn(total=2, solved=1, unmark_rowcount=0)
    pblib.check_round_completion(7, conn)
    conn.commit.assert_not_called()
    quiet.assert_not_called()


def test_round_id_is_parameterised_not_interpolated(quiet):
    conn, cursor = _conn(total=1, solved=1)
    pblib.check_round_completion("7", conn)
    for call in cursor.execute.call_args_list:
        assert "7" not in str(call.args[0]), "round id must be a bound parameter"
        if len(call.args) > 1:
            assert call.args[1] == (7,) or 7 in call.args[1]


def test_a_database_error_is_swallowed(quiet):
    """A failure here must never break the solve path that called it."""
    conn = MagicMock()
    conn.cursor.side_effect = RuntimeError("db gone")
    with patch.object(pblib, "debug_log", MagicMock()) as log:
        pblib.check_round_completion(7, conn)   # must not raise
    assert any(c.args[0] == 1 for c in log.call_args_list), "the error must be logged at SEV1"
