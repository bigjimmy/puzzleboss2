#!/usr/bin/env python3
"""bigjimmybot._check_puzzle_from_queue — the worker loop.

This loop was rewritten to fix two production faults at once: it used to
busy-wait on an empty queue, and a puzzle that raised could leave the
queue's unfinished count wrong so a join() never returned. Both are
invisible until the hunt is large enough to matter, which is exactly when
you cannot afford them.

The properties worth pinning down: every item is drained even when some
raise, task_done() is called once per get() no matter what, an empty
queue blocks rather than spins, and EXIT_FLAG ends the loop.

Run with: pytest tests/test_bigjimmybot_queue.py -v
"""

import os
import queue
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def bjb():
    """Import bigjimmybot with its DB/Google dependencies stubbed, restoring
    sys.modules afterwards so other test files still see the real pblib."""
    saved = {n: sys.modules.get(n) for n in
             ("MySQLdb", "MySQLdb.cursors", "pbgooglelib", "pblib")}
    sys.modules["MySQLdb"] = MagicMock()
    sys.modules["MySQLdb.cursors"] = MagicMock()
    sys.modules["pbgooglelib"] = MagicMock()
    pblib_mock = MagicMock()
    pblib_mock.config = {"MYSQL": {"HOST": "h", "USERNAME": "u",
                                   "PASSWORD": "p", "DATABASE": "d"}}
    pblib_mock.configstruct = {"BIGJIMMY_AUTOASSIGN": "true"}
    pblib_mock.debug_log = lambda level, msg: None
    sys.modules["pblib"] = pblib_mock
    if isinstance(sys.modules.get("bigjimmybot"), MagicMock):
        del sys.modules["bigjimmybot"]
    import bigjimmybot as mod
    yield mod
    for name, orig in saved.items():
        if orig is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = orig


def _run_worker(bjb, q, processed, fail_on=(), timeout=5):
    """Run the loop in a thread until the queue drains, then stop it."""
    def fake_process(puzzle, threadname):
        processed.append(puzzle["name"])
        if puzzle["name"] in fail_on:
            raise RuntimeError(f"boom on {puzzle['name']}")

    bjb.EXIT_FLAG = 0
    with patch.object(bjb, "_process_puzzle", fake_process), \
         patch.object(bjb, "debug_log", lambda *a, **k: None):
        t = threading.Thread(target=bjb._check_puzzle_from_queue,
                             args=("testthread", q), daemon=True)
        t.start()
        deadline = time.time() + timeout
        while q.unfinished_tasks and time.time() < deadline:
            time.sleep(0.01)
        bjb.EXIT_FLAG = 1
        t.join(timeout=timeout)
    return t


def test_drains_every_item(bjb):
    q = queue.Queue()
    names = [f"puzzle{i}" for i in range(50)]
    for n in names:
        q.put({"name": n})
    processed = []
    t = _run_worker(bjb, q, processed)
    assert not t.is_alive(), "worker did not exit on EXIT_FLAG"
    assert processed == names
    assert q.unfinished_tasks == 0, "task_done() was not called for every item"


def test_a_failing_puzzle_does_not_stall_the_queue(bjb):
    """The original fault: an exception skipped task_done(), so the counter
    never reached zero and join() hung forever."""
    q = queue.Queue()
    for n in ["ok1", "bad", "ok2"]:
        q.put({"name": n})
    processed = []
    _run_worker(bjb, q, processed, fail_on=("bad",))
    assert processed == ["ok1", "bad", "ok2"], "a raising puzzle must not stop the worker"
    assert q.unfinished_tasks == 0, "task_done() must run even when processing raised"
    q.join()  # would hang if the count were wrong


def test_more_items_than_the_production_queue_bound(bjb):
    """WORK_QUEUE is bounded at 300; the 2026 hunt ran ~275 puzzles and the
    deadlock showed up as the count approached the bound."""
    assert bjb.WORK_QUEUE.maxsize == 300
    q = queue.Queue()
    for i in range(400):
        q.put({"name": f"p{i}"})
    processed = []
    _run_worker(bjb, q, processed, fail_on={f"p{i}" for i in range(0, 400, 7)}, timeout=10)
    assert len(processed) == 400
    assert q.unfinished_tasks == 0


def test_empty_queue_blocks_instead_of_spinning(bjb):
    """The loop must wait on get(timeout=...), not spin. A busy-wait would
    burn a core per thread between scan cycles."""
    q = queue.Queue()
    calls = {"n": 0}
    real_get = q.get

    # Count only. An assertion in here would raise inside the worker thread,
    # killing the loop and making the call-count check pass vacuously — which
    # is exactly what an earlier version of this test did.
    def counting_get(*a, **kw):
        calls["n"] += 1
        return real_get(*a, **kw)

    bjb.EXIT_FLAG = 0
    with patch.object(bjb, "debug_log", lambda *a, **k: None), \
         patch.object(q, "get", counting_get):
        t = threading.Thread(target=bjb._check_puzzle_from_queue,
                             args=("idlethread", q), daemon=True)
        t.start()
        time.sleep(2.2)
        bjb.EXIT_FLAG = 1
        t.join(timeout=5)
    assert not t.is_alive(), "worker thread died; it should have been idling"
    # One blocking get per ~1s timeout: a handful over 2.2s. A get_nowait spin
    # would be many thousands.
    assert calls["n"] <= 10, f"looks like a busy-wait: {calls['n']} get() calls in 2.2s"


def test_exit_flag_stops_a_busy_worker(bjb):
    q = queue.Queue()
    for i in range(5):
        q.put({"name": f"x{i}"})
    processed = []
    t = _run_worker(bjb, q, processed)
    assert not t.is_alive()
    assert bjb._check_puzzle_from_queue.__doc__, "keep the docstring; it explains the fix"
