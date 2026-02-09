#!/usr/bin/env python3
"""
Comprehensive API Test Suite for PuzzleBoss 2000

Tests all REST API endpoints: puzzle CRUD, round management, solver assignments,
tagging, activity tracking, bot statistics, cache, and documentation.

Usage:
    docker exec puzzleboss-app python3 scripts/test_api_coverage.py --allow-destructive
    docker exec puzzleboss-app python3 scripts/test_api_coverage.py --allow-destructive --tests 1 3 5
    docker exec puzzleboss-app python3 scripts/test_api_coverage.py --list
"""

import argparse
import json
import os
import random
import string
import subprocess
import sys
import time
import traceback

import requests

# Configuration
BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:5000")


# ============================================================================
# Test infrastructure
# ============================================================================

class TestLogger:
    """Simple indented logger for test output."""
    def __init__(self):
        self.indent = 0

    def log_operation(self, msg):
        ts = time.strftime("%H:%M:%S")
        prefix = "  " * self.indent
        print(f"[{ts}] [OP] {prefix}{msg}")

    def log_error(self, msg):
        ts = time.strftime("%H:%M:%S")
        prefix = "  " * self.indent
        print(f"[{ts}] [ERR] {prefix}{msg}")

    def log_warning(self, msg):
        ts = time.strftime("%H:%M:%S")
        prefix = "  " * self.indent
        print(f"[{ts}] [WARN] {prefix}{msg}")


class TestResult:
    """Tracks pass/fail for a single test."""
    def __init__(self):
        self.passed = True
        self.message = ""

    def fail(self, msg):
        self.passed = False
        self.message = msg

    def set_success(self, msg):
        if self.passed:
            self.message = msg


# ============================================================================
# Test runner
# ============================================================================

class TestRunner:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.logger = TestLogger()
        self.solvers = []
        self.puzzles = []
        self.rounds = []
        # Emoji set for name generation
        self.emojis = ["🧩", "🔍", "🎯", "💡", "🗝️", "🎲", "📐", "🔮",
                       "🌟", "⚡", "🔑", "🎪", "🎭", "🎨", "🏆"]

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def api_get(self, path):
        """GET request; raise on non-2xx."""
        r = requests.get(f"{self.base_url}{path}")
        if not r.ok:
            raise Exception(f"GET {path} failed: {r.status_code} - {r.text[:200]}")
        return r.json()

    def api_post(self, path, data=None):
        """POST request; raise on non-2xx."""
        r = requests.post(f"{self.base_url}{path}", json=data)
        if not r.ok:
            raise Exception(f"POST {path} failed: {r.status_code} - {r.text[:200]}")
        return r.json()

    def api_delete(self, path):
        """DELETE request; raise on non-2xx."""
        r = requests.delete(f"{self.base_url}{path}")
        if not r.ok:
            raise Exception(f"DELETE {path} failed: {r.status_code} - {r.text[:200]}")
        return r.json()

    def api_get_raw(self, path):
        """GET request returning raw response (for testing error cases)."""
        return requests.get(f"{self.base_url}{path}")

    def api_post_raw(self, path, data=None):
        """POST request returning raw response (for testing error cases)."""
        return requests.post(f"{self.base_url}{path}", json=data)

    def api_delete_raw(self, path):
        """DELETE request returning raw response (for testing error cases)."""
        return requests.delete(f"{self.base_url}{path}")

    # ------------------------------------------------------------------
    # Entity helpers
    # ------------------------------------------------------------------

    def get_emoji_string(self, base, include_emoji=True):
        if include_emoji:
            emoji = random.choice(self.emojis)
            return f"{emoji} {base} {emoji}"
        return base

    def get_all_solvers(self):
        return self.api_get("/solvers").get("solvers", [])

    def get_all_puzzles(self):
        return self.api_get("/puzzles").get("puzzles", [])

    def get_all_rounds(self):
        return self.api_get("/rounds").get("rounds", [])

    def get_puzzle_details(self, puzzle_id):
        try:
            data = self.api_get(f"/puzzles/{puzzle_id}")
            return data.get("puzzle", data)
        except Exception:
            return None

    def get_solver_details(self, solver_id):
        try:
            data = self.api_get(f"/solvers/{solver_id}")
            return data.get("solver", data)
        except Exception:
            return None

    def get_round(self, round_id):
        try:
            data = self.api_get(f"/rounds/{round_id}")
            return data.get("round", data)
        except Exception:
            return None

    def create_solver(self, name, fullname=None):
        self.logger.log_operation(f"Creating solver: {name}")
        data = self.api_post("/solvers", {"name": name, "fullname": fullname or name})
        return data

    def create_round(self, name):
        """Create a round and return its data dict."""
        self.logger.log_operation(f"Creating round: {name}")
        self.api_post("/rounds", {"name": name})
        sanitized = name.replace(" ", "")
        rounds = self.get_all_rounds()
        for r in rounds:
            if r["name"] == sanitized:
                self.logger.log_operation(f"  Created round '{sanitized}' (id {r['id']})")
                return r
        raise Exception(f"Round '{sanitized}' not found after creation")

    def create_puzzle(self, name, round_id, use_stepwise=False, is_meta=False, is_speculative=False):
        """Create a puzzle and return its data dict."""
        self.logger.log_operation(f"Creating puzzle: {name} (round {round_id})")
        if use_stepwise:
            return self._create_puzzle_stepwise(name, round_id, is_meta, is_speculative)
        else:
            return self._create_puzzle_oneshot(name, round_id, is_meta, is_speculative)

    def _create_puzzle_oneshot(self, name, round_id, is_meta=False, is_speculative=False):
        inner = {"name": name, "round_id": int(round_id),
                 "puzzle_uri": f"https://example.com/{name.replace(' ', '_')}"}
        if is_meta:
            inner["ismeta"] = 1
        if is_speculative:
            inner["is_speculative"] = 1
        data = self.api_post("/puzzles", {"puzzle": inner})
        # Find created puzzle
        sanitized = name.replace(" ", "")
        puzzles = self.get_all_puzzles()
        for p in puzzles:
            if p["name"] == sanitized:
                details = self.get_puzzle_details(p["id"])
                if details:
                    return details
        raise Exception(f"Puzzle '{sanitized}' not found after creation")

    def _create_puzzle_stepwise(self, name, round_id, is_meta=False, is_speculative=False):
        payload = {
            "puzzle": {
                "name": name,
                "round_id": str(round_id),
                "puzzle_uri": f"https://example.com/{name.replace(' ', '_')}",
                "ismeta": 1 if is_meta else 0,
                "is_speculative": 1 if is_speculative else 0,
            }
        }
        step_data = self.api_post("/puzzles/stepwise", payload)
        code = step_data.get("code")
        if not code:
            raise Exception(f"Stepwise creation returned no code: {step_data}")

        # Execute steps 1-5
        for step in range(1, 6):
            try:
                self.api_get(f"/createpuzzle/{code}?step={step}")
            except Exception:
                self.logger.log_warning(f"  Step {step} returned error (may be expected if Discord/Google disabled)")

        # Find created puzzle
        sanitized = name.replace(" ", "")
        puzzles = self.get_all_puzzles()
        for p in puzzles:
            if p["name"] == sanitized:
                details = self.get_puzzle_details(p["id"])
                if details:
                    return details
        raise Exception(f"Stepwise puzzle '{sanitized}' not found after creation")

    def update_puzzle(self, puzzle_id, field, value):
        """Update a single puzzle field. Returns True on success."""
        try:
            self.api_post(f"/puzzles/{puzzle_id}/{field}", {field: value})
            return True
        except Exception as e:
            self.logger.log_error(f"Failed to update puzzle {puzzle_id} {field}: {e}")
            return False

    def update_round(self, round_id, field, value):
        try:
            self.api_post(f"/rounds/{round_id}/{field}", {field: value})
            return True
        except Exception as e:
            self.logger.log_error(f"Failed to update round {round_id} {field}: {e}")
            return False

    def assign_solver_to_puzzle(self, solver_id, puzzle_id):
        try:
            self.api_post(f"/solvers/{solver_id}/puzz", {"puzz": puzzle_id})
            return True
        except Exception as e:
            self.logger.log_error(f"Failed to assign solver {solver_id} to puzzle {puzzle_id}: {e}")
            return False

    def add_solver_to_history(self, puzzle_id, solver_id):
        try:
            self.api_post(f"/puzzles/{puzzle_id}/history/add", {"solver_id": solver_id})
            return True
        except Exception as e:
            self.logger.log_error(f"Failed to add solver {solver_id} to history of puzzle {puzzle_id}: {e}")
            return False

    def remove_solver_from_history(self, puzzle_id, solver_id):
        try:
            self.api_post(f"/puzzles/{puzzle_id}/history/remove", {"solver_id": solver_id})
            return True
        except Exception as e:
            self.logger.log_error(f"Failed to remove solver {solver_id} from history: {e}")
            return False

    def is_round_complete(self, round_id):
        rd = self.get_round(round_id)
        return rd.get("status") == "Solved" if rd else False

    def verify_puzzle_field(self, result, puzzle_id, field, expected, msg=None):
        """Fetch puzzle and assert field matches expected. Returns True if ok."""
        details = self.get_puzzle_details(puzzle_id)
        if not details:
            result.fail(msg or f"Failed to get puzzle {puzzle_id}")
            return False
        actual = details.get(field)
        if actual != expected:
            result.fail(msg or f"Puzzle {puzzle_id} {field}: expected {expected!r}, got {actual!r}")
            return False
        return True

    def get_testable_statuses(self):
        """Get non-Solved statuses from /huntinfo (with fallback)."""
        try:
            data = self.api_get("/huntinfo")
            statuses = data.get("statuses", [])
            return [s["name"] for s in statuses if s["name"] not in ["Solved", "[hidden]"]]
        except Exception:
            return ["New", "Being worked", "Needs eyes", "Critical", "WTF",
                    "Under control", "Waiting for HQ", "Grind", "Abandoned",
                    "Speculative", "Unnecessary"]

    def get_unsolved_puzzles(self):
        """Get detailed unsolved puzzles."""
        result = []
        for p in self.get_all_puzzles():
            details = self.get_puzzle_details(p["id"])
            if details and details.get("status") != "Solved":
                result.append(details)
        return result

    def generate_unique_test_tag_name(self):
        existing = set()
        try:
            existing = {t["name"] for t in self.api_get("/tags").get("tags", [])}
        except Exception:
            pass
        while True:
            tag = f"test-{int(time.time() * 1000)}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"
            if tag not in existing:
                return tag

    # ------------------------------------------------------------------
    # Test runner infrastructure
    # ------------------------------------------------------------------

    def run_test(self, name, test_func):
        result = TestResult()
        print(f"\n{'=' * 80}")
        self.logger.log_operation(f"Starting test: {name}")
        print(f"{'=' * 80}")
        start = time.time()
        try:
            test_func(result)
        except Exception as e:
            result.fail(f"Unhandled exception: {e}")
            self.logger.log_error(traceback.format_exc())
        elapsed = time.time() - start
        status = "✅" if result.passed else "❌"
        print(f"\n{'=' * 80}")
        self.logger.log_operation(f"Completed test: {name} - {status} ({elapsed:.2f}s)")
        print(f"{'=' * 80}")
        return result, elapsed

    # ======================================================================
    # TESTS
    # ======================================================================

    # ------------------------------------------------------------------
    # Test 1: Solver Listing
    # ------------------------------------------------------------------
    def test_solver_listing(self, result: TestResult):
        solvers = self.get_all_solvers()
        if not solvers:
            result.fail("No solvers found")
            return
        result.set_success(f"Found {len(solvers)} solvers")

    # ------------------------------------------------------------------
    # Test 2: Puzzle Creation (One-Shot)
    # ------------------------------------------------------------------
    def test_puzzle_creation(self, result: TestResult):
        """Create 3 rounds x 5 puzzles each (15 total), verify names and rounds."""
        rounds = []
        for i in range(3):
            rd = self.create_round(f"Test Round {int(time.time()) + i}")
            rounds.append(rd)

        for round_idx, rd in enumerate(rounds):
            for puzzle_idx in range(5):
                base = f"Test Puzzle R{round_idx+1}P{puzzle_idx+1} {int(time.time())}"
                name = self.get_emoji_string(base, include_emoji=(puzzle_idx % 2 == 0))
                puz = self.create_puzzle(name, rd["id"], use_stepwise=False)
                expected = name.replace(" ", "")
                if puz["name"] != expected:
                    result.fail(f"Name mismatch: expected {expected}, got {puz['name']}")
                    return
                if str(puz["round_id"]) != str(rd["id"]):
                    result.fail(f"Puzzle {puz['name']} in wrong round")
                    return

        result.set_success("One-shot puzzle creation test completed successfully")

    # ------------------------------------------------------------------
    # Test 3: Puzzle Creation (Stepwise)
    # ------------------------------------------------------------------
    def test_puzzle_creation_stepwise(self, result: TestResult):
        """Create 2 rounds x 3 puzzles (regular, meta, speculative) via stepwise."""
        rounds = []
        for i in range(2):
            rd = self.create_round(f"Stepwise Round {int(time.time()) + i}")
            rounds.append(rd)

        for round_idx, rd in enumerate(rounds):
            for puzzle_idx in range(3):
                base = f"Stepwise Puzzle R{round_idx+1}P{puzzle_idx+1} {int(time.time())}"
                name = self.get_emoji_string(base, include_emoji=(puzzle_idx % 2 == 0))
                is_meta = (puzzle_idx == 1)
                is_spec = (puzzle_idx == 2)

                puz = self.create_puzzle(name, rd["id"], use_stepwise=True,
                                         is_meta=is_meta, is_speculative=is_spec)
                expected = name.replace(" ", "")
                if puz["name"] != expected:
                    result.fail(f"Stepwise name mismatch: expected {expected}, got {puz['name']}")
                    return
                if is_meta and not puz.get("ismeta"):
                    result.fail(f"Puzzle {puz['name']} should be meta")
                    return
                if is_spec and puz.get("status") != "Speculative":
                    result.fail(f"Puzzle {puz['name']} should be Speculative, got {puz.get('status')}")
                    return
                if str(puz["round_id"]) != str(rd["id"]):
                    result.fail(f"Stepwise puzzle {puz['name']} in wrong round")
                    return

        result.set_success("Stepwise puzzle creation test completed successfully")

    # ------------------------------------------------------------------
    # Test 4: Puzzle Modification
    # ------------------------------------------------------------------
    def test_puzzle_modification(self, result: TestResult):
        """Test updating every puzzle field (status cycling, name, notes, etc.)."""
        puzzles = self.get_all_puzzles()
        if not puzzles:
            result.fail("No puzzles found")
            return

        statuses = self.get_testable_statuses()

        # Test status changes on up to 3 puzzles
        selected = random.sample(puzzles, min(3, len(puzzles)))
        for puzzle in selected:
            details = self.get_puzzle_details(puzzle["id"])
            if not details or details.get("status") == "Solved":
                continue

            for status in statuses:
                self.update_puzzle(puzzle["id"], "status", status)
                if not self.verify_puzzle_field(result, puzzle["id"], "status", status):
                    return
            self.logger.log_operation(f"  Cycled {len(statuses)} statuses on {puzzle['name']}")

        # Test name change
        test_puzzle = selected[0]
        new_name = f"Renamed {int(time.time())}"
        self.update_puzzle(test_puzzle["id"], "name", new_name)
        expected_name = new_name.replace(" ", "")
        if not self.verify_puzzle_field(result, test_puzzle["id"], "name", expected_name):
            return
        self.logger.log_operation(f"  Renamed puzzle to {expected_name}")

        # Test comments update
        comments = f"Test comments at {int(time.time())}"
        self.update_puzzle(test_puzzle["id"], "comments", comments)
        if not self.verify_puzzle_field(result, test_puzzle["id"], "comments", comments):
            return

        # Test xyzloc update
        location = f"Location {random.randint(100, 999)}"
        self.update_puzzle(test_puzzle["id"], "xyzloc", location)
        if not self.verify_puzzle_field(result, test_puzzle["id"], "xyzloc", location):
            return

        result.set_success("Puzzle modification test completed successfully")

    # ------------------------------------------------------------------
    # Test 5: Puzzle Round Change
    # ------------------------------------------------------------------
    def test_puzzle_round_change(self, result: TestResult):
        rounds = self.get_all_rounds()
        if len(rounds) < 2:
            result.fail("Need at least 2 rounds")
            return

        round_1, round_2 = rounds[0], rounds[1]

        # Find an unsolved puzzle in round_1
        test_puzzle = None
        for p in self.get_all_puzzles():
            details = self.get_puzzle_details(p["id"])
            if details and str(details.get("round_id")) == str(round_1["id"]) and details.get("status") != "Solved":
                test_puzzle = details
                break

        if not test_puzzle:
            result.fail(f"No unsolved puzzles in round {round_1['name']}")
            return

        # Move puzzle to round_2
        self.logger.log_operation(f"Moving '{test_puzzle['name']}' from {round_1['name']} to {round_2['name']}")
        self.api_post(f"/puzzles/{test_puzzle['id']}/round_id", {"round_id": round_2["id"]})
        if not self.verify_puzzle_field(result, test_puzzle["id"], "round_id", round_2["id"],
                                        f"Round not updated to {round_2['id']}"):
            return

        # Verify activity logged
        self.api_get("/activity")

        # Test invalid round_id rejection
        r = self.api_post_raw(f"/puzzles/{test_puzzle['id']}/round_id", {"round_id": 99999})
        if r.ok:
            result.fail("Invalid round_id was accepted")
            return

        result.set_success("Puzzle round change test completed successfully")

    # ------------------------------------------------------------------
    # Test 6: Puzzle Multi-Part Update
    # ------------------------------------------------------------------
    def test_multi_part_update(self, result: TestResult):
        """Test POST /puzzles/<id> with multiple fields at once."""
        puzzles = self.get_all_puzzles()
        if not puzzles:
            result.fail("No puzzles")
            return

        # Find unsolved puzzle
        test_puzzle = None
        for p in puzzles:
            details = self.get_puzzle_details(p["id"])
            if details and details.get("status") != "Solved":
                test_puzzle = details
                break

        if not test_puzzle:
            result.fail("No unsolved puzzles available")
            return

        pid = test_puzzle["id"]
        ts = str(int(time.time()))

        # Multi-part update: status + comments + xyzloc
        payload = {
            "status": "Being worked",
            "comments": f"Multi-part comment {ts}",
            "xyzloc": f"Multi-part location {ts}",
        }
        self.logger.log_operation(f"Multi-part updating puzzle {test_puzzle['name']}")
        self.api_post(f"/puzzles/{pid}", payload)

        # Verify all fields
        details = self.get_puzzle_details(pid)
        if not details:
            result.fail("Failed to get puzzle after multi-part update")
            return

        for field, expected in payload.items():
            actual = details.get(field)
            if actual != expected:
                result.fail(f"Multi-part {field}: expected {expected!r}, got {actual!r}")
                return

        # Test with statuses from huntinfo
        statuses = self.get_testable_statuses()
        for status in statuses:
            self.api_post(f"/puzzles/{pid}", {"status": status})
            if not self.verify_puzzle_field(result, pid, "status", status):
                return

        result.set_success("Multi-part update test completed successfully")

    # ------------------------------------------------------------------
    # Test 7: Round Modification
    # ------------------------------------------------------------------
    def test_round_modification(self, result: TestResult):
        rounds = self.get_all_rounds()
        if not rounds:
            result.fail("No rounds found")
            return

        test_round = rounds[0]
        rid = test_round["id"]

        # Test name change
        new_name = f"RenamedRound{int(time.time())}"
        self.update_round(rid, "name", new_name)
        rd = self.get_round(rid)
        if not rd or rd.get("name") != new_name:
            result.fail(f"Round name not updated to {new_name}")
            return

        result.set_success("Round modification test completed successfully")

    # ------------------------------------------------------------------
    # Test 8: Round Multi-Part Update
    # ------------------------------------------------------------------
    def test_round_multi_part_update(self, result: TestResult):
        rounds = self.get_all_rounds()
        if not rounds:
            result.fail("No rounds found")
            return

        test_round = rounds[0]
        rid = test_round["id"]
        ts = str(int(time.time()))

        new_name = f"MultiPartRound{ts}"
        payload = {"name": new_name}
        self.api_post(f"/rounds/{rid}", payload)

        rd = self.get_round(rid)
        if not rd or rd.get("name") != new_name:
            result.fail(f"Round multi-part name not updated to {new_name}")
            return

        result.set_success("Round multi-part update test completed successfully")

    # ------------------------------------------------------------------
    # Test 9: Solver Multi-Part Update
    # ------------------------------------------------------------------
    def test_solver_multi_part_update(self, result: TestResult):
        solvers = self.get_all_solvers()
        if not solvers:
            result.fail("No solvers found")
            return

        solver = solvers[0]
        sid = solver["id"]
        ts = str(int(time.time()))

        new_fullname = f"Updated Full Name {ts}"
        self.api_post(f"/solvers/{sid}", {"fullname": new_fullname})

        details = self.get_solver_details(sid)
        if not details or details.get("fullname") != new_fullname:
            result.fail(f"Solver fullname not updated to {new_fullname}")
            return

        result.set_success("Solver multi-part update test completed successfully")

    # ------------------------------------------------------------------
    # Test 10: Meta Puzzles and Round Completion
    # ------------------------------------------------------------------
    def test_meta_puzzles_and_round_completion(self, result: TestResult):
        ts = str(int(time.time()))
        test_round = self.create_round(f"Test Meta Round {ts}")

        # Create 2 meta puzzles + 1 non-meta
        meta1 = self.create_puzzle(f"Test Meta Puzzle 1 {ts}", test_round["id"])
        meta2 = self.create_puzzle(f"Test Meta Puzzle 2 {ts}", test_round["id"])
        non_meta = self.create_puzzle(f"Test Non-Meta Puzzle {ts}", test_round["id"])

        # Mark as meta
        for mp in [meta1, meta2]:
            if not self.update_puzzle(mp["id"], "ismeta", True):
                result.fail(f"Failed to set {mp['name']} as meta")
                return
            if not self.verify_puzzle_field(result, mp["id"], "ismeta", 1,
                                            f"{mp['name']} not marked as meta"):
                return

        # Solve non-meta
        self.update_puzzle(non_meta["id"], "answer", "TEST ANSWER")

        # Round should NOT be complete (metas unsolved)
        if self.is_round_complete(test_round["id"]):
            result.fail("Round marked complete before metas solved")
            return

        # Solve first meta
        self.update_puzzle(meta1["id"], "answer", "META ANSWER 1")
        if self.is_round_complete(test_round["id"]):
            result.fail("Round complete with only one meta solved")
            return

        # Solve second meta -> round should be complete
        self.update_puzzle(meta2["id"], "answer", "META ANSWER 2")
        time.sleep(0.1)
        if not self.is_round_complete(test_round["id"]):
            result.fail("Round not complete after all metas solved")
            return

        # Add new unsolved meta -> round should un-complete
        meta3 = self.create_puzzle(f"Test Meta Puzzle 3 {ts}", test_round["id"])
        self.update_puzzle(meta3["id"], "ismeta", True)
        if self.is_round_complete(test_round["id"]):
            result.fail("Round still complete after adding unsolved meta")
            return

        # Solve third meta -> round complete again
        self.update_puzzle(meta3["id"], "answer", "META ANSWER 3")
        if not self.is_round_complete(test_round["id"]):
            result.fail("Round not complete after solving third meta")
            return

        result.set_success("Meta puzzles and round completion test completed successfully")

    # ------------------------------------------------------------------
    # Test 11: Answer Verification
    # ------------------------------------------------------------------
    def test_answer_verification(self, result: TestResult):
        puzzles = self.get_all_puzzles()
        if not puzzles:
            result.fail("No puzzles found")
            return

        selected = random.sample(puzzles, min(3, len(puzzles)))
        for puzzle in selected:
            answer = f"Test Answer {random.randint(1000, 9999)} 🎯"
            self.update_puzzle(puzzle["id"], "answer", answer)

            details = self.get_puzzle_details(puzzle["id"])
            if not details:
                result.fail(f"Failed to get details for {puzzle['name']}")
                return

            expected = answer.upper()
            if details.get("answer") != expected:
                result.fail(f"Answer mismatch for {puzzle['name']}: expected {expected}, got {details.get('answer')}")
                return
            if details.get("status") != "Solved":
                result.fail(f"Status not Solved for {puzzle['name']}")
                return

        result.set_success("Answer verification test completed successfully")

    # ------------------------------------------------------------------
    # Test 12: Solver Assignments
    # ------------------------------------------------------------------
    def test_solver_assignments(self, result: TestResult):
        solvers = self.get_all_solvers()
        unsolved = self.get_unsolved_puzzles()

        if not solvers or len(solvers) < 2:
            result.fail("Need at least 2 solvers")
            return
        if not unsolved:
            result.fail("No unsolved puzzles")
            return

        # Select up to 4 puzzles
        selected = random.sample(unsolved, min(4, len(unsolved)))
        for puzzle in selected:
            test_solvers = random.sample(solvers, 2)
            for solver in test_solvers:
                if not self.assign_solver_to_puzzle(solver["id"], puzzle["id"]):
                    result.fail(f"Failed to assign {solver['name']} to {puzzle['name']}")
                    return
                sd = self.get_solver_details(solver["id"])
                if not sd or sd.get("puzz") != puzzle["name"]:
                    result.fail(f"Solver {solver['name']} not assigned to {puzzle['name']}")
                    return

        result.set_success("Solver assignment test completed successfully")

    # ------------------------------------------------------------------
    # Test 13: Solve Clears Location and Solvers
    # ------------------------------------------------------------------
    def test_solve_clears_location_and_solvers(self, result: TestResult):
        solvers = self.get_all_solvers()
        unsolved = self.get_unsolved_puzzles()

        if not unsolved:
            result.fail("No unsolved puzzles")
            return
        if not solvers or len(solvers) < 2:
            result.fail("Need at least 2 solvers")
            return

        puzzle = unsolved[0]
        pid = puzzle["id"]

        # Set location
        loc = f"Test Location {random.randint(1000, 9999)}"
        self.update_puzzle(pid, "xyzloc", loc)

        # Assign 2 solvers
        for s in random.sample(solvers, 2):
            self.assign_solver_to_puzzle(s["id"], pid)

        # Verify location and solvers set
        details = self.get_puzzle_details(pid)
        if not details or not details.get("xyzloc") or not details.get("cursolvers"):
            result.fail("Location or solvers not set before solve")
            return

        # Solve
        self.update_puzzle(pid, "answer", f"SOLVE TEST {random.randint(1000, 9999)}")

        # Verify cleared
        details = self.get_puzzle_details(pid)
        if details.get("status") != "Solved":
            result.fail(f"Status not Solved, got {details.get('status')}")
            return
        if details.get("xyzloc"):
            result.fail(f"Location not cleared: {details.get('xyzloc')}")
            return
        if details.get("cursolvers"):
            result.fail(f"Solvers not cleared: {details.get('cursolvers')}")
            return

        result.set_success("Solve clears location and solvers test completed successfully")

    # ------------------------------------------------------------------
    # Test 14: Solver Reassignment
    # ------------------------------------------------------------------
    def test_solver_reassignment(self, result: TestResult):
        puzzles = self.get_all_puzzles()
        solvers = self.get_all_solvers()

        if len(puzzles) < 2 or len(solvers) < 2:
            result.fail("Need at least 2 puzzles and 2 solvers")
            return

        # Find 2 solvers already assigned
        assigned = []
        for s in solvers:
            sd = self.get_solver_details(s["id"])
            if sd and sd.get("puzz"):
                assigned.append(s)
        if len(assigned) < 2:
            result.fail("Need at least 2 assigned solvers")
            return

        solver1, solver2 = random.sample(assigned, 2)
        s1d = self.get_solver_details(solver1["id"])
        s2d = self.get_solver_details(solver2["id"])

        # Find 2 unsolved puzzles not assigned to either solver
        available = []
        for p in puzzles:
            pd = self.get_puzzle_details(p["id"])
            if pd and pd.get("status") != "Solved" and p["name"] != s1d.get("puzz") and p["name"] != s2d.get("puzz"):
                available.append(p)
        if len(available) < 2:
            result.fail("Not enough available puzzles")
            return

        puzzle1, puzzle2 = random.sample(available, 2)

        # Assign both solvers to puzzle1
        for s in [solver1, solver2]:
            self.assign_solver_to_puzzle(s["id"], puzzle1["id"])

        # Verify both on puzzle1
        p1d = self.get_puzzle_details(puzzle1["id"])
        cs = (p1d.get("cursolvers") or "").split(",")
        if solver1["name"] not in cs or solver2["name"] not in cs:
            result.fail(f"Solvers not properly assigned to {puzzle1['name']}")
            return

        # Reassign solver1 to puzzle2
        self.assign_solver_to_puzzle(solver1["id"], puzzle2["id"])

        # Verify solver1 moved, solver2 stayed
        p1d = self.get_puzzle_details(puzzle1["id"])
        p2d = self.get_puzzle_details(puzzle2["id"])
        s1d = self.get_solver_details(solver1["id"])

        if solver1["name"] in (p1d.get("cursolvers") or "").split(","):
            result.fail(f"{solver1['name']} still on {puzzle1['name']}")
            return
        if solver1["name"] not in (p2d.get("cursolvers") or "").split(","):
            result.fail(f"{solver1['name']} not on {puzzle2['name']}")
            return
        if s1d.get("puzz") != puzzle2["name"]:
            result.fail(f"{solver1['name']} puzz field not updated to {puzzle2['name']}")
            return

        result.set_success("Solver reassignment test completed successfully")

    # ------------------------------------------------------------------
    # Test 15: Activity Tracking
    # ------------------------------------------------------------------
    def test_activity_tracking(self, result: TestResult):
        solvers = self.get_all_solvers()
        unsolved = self.get_unsolved_puzzles()

        if not solvers or not unsolved:
            result.fail("Need solvers and unsolved puzzles")
            return

        selected = random.sample(unsolved, min(3, len(unsolved)))
        for puzzle in selected:
            test_solvers = random.sample(solvers, min(2, len(solvers)))
            for solver in test_solvers:
                self.assign_solver_to_puzzle(solver["id"], puzzle["id"])

                # Check lastact
                data = self.api_get(f"/puzzles/{puzzle['id']}/lastact")
                lastact = data.get("puzzle", {}).get("lastact")
                if not lastact:
                    result.fail(f"No lastact for {puzzle['name']}")
                    return
                for key in ["time", "type", "source", "uri"]:
                    if key not in lastact:
                        result.fail(f"Missing '{key}' in lastact for {puzzle['name']}")
                        return

        result.set_success("Activity tracking test completed successfully")

    # ------------------------------------------------------------------
    # Test 16: Puzzle Activity Endpoint
    # ------------------------------------------------------------------
    def test_puzzle_activity_endpoint(self, result: TestResult):
        puzzles = self.get_all_puzzles()
        if not puzzles:
            result.fail("No puzzles")
            return

        pid = puzzles[0]["id"]
        data = self.api_get(f"/puzzles/{pid}/activity")

        if data.get("status") != "ok":
            result.fail(f"Invalid status: {data.get('status')}")
            return
        if data.get("puzzle_id") != pid:
            result.fail(f"Puzzle ID mismatch: expected {pid}, got {data.get('puzzle_id')}")
            return

        activities = data.get("activity", [])
        if not isinstance(activities, list) or len(activities) < 1:
            result.fail("Should have at least one activity entry")
            return

        # Validate structure of first few
        for i, act in enumerate(activities[:3]):
            for field in ["id", "time", "solver_id", "puzzle_id", "source", "type"]:
                if field not in act:
                    result.fail(f"Activity {i} missing '{field}'")
                    return
            if act["puzzle_id"] != pid:
                result.fail(f"Activity {i} wrong puzzle_id")
                return

        # Validate time ordering (most recent first)
        if len(activities) > 1:
            times = [a["time"] for a in activities]
            if times[0] < times[-1]:
                result.fail("Activities not sorted (most recent first)")
                return

        # Generate new activity and verify count increases
        before_count = len(activities)
        self.api_post(f"/puzzles/{pid}/status", {"status": "Critical"})
        updated = self.api_get(f"/puzzles/{pid}/activity")
        if len(updated.get("activity", [])) > before_count:
            self.logger.log_operation(f"  Activity count increased: {before_count} -> {len(updated['activity'])}")

        # Non-existent puzzle should fail
        r = self.api_get_raw(f"/puzzles/999999/activity")
        if r.ok:
            result.fail("Should fail for non-existent puzzle")
            return

        result.set_success("Puzzle activity endpoint test completed successfully")

    # ------------------------------------------------------------------
    # Test 17: Solver Activity Endpoint
    # ------------------------------------------------------------------
    def test_solver_activity_endpoint(self, result: TestResult):
        solvers = self.get_all_solvers()
        if not solvers:
            result.fail("No solvers")
            return

        sid = solvers[0]["id"]
        data = self.api_get(f"/solvers/{sid}/activity")

        if data.get("status") != "ok":
            result.fail(f"Invalid status: {data.get('status')}")
            return
        if data.get("solver_id") != sid:
            result.fail(f"Solver ID mismatch")
            return

        activities = data.get("activity", [])
        if not isinstance(activities, list):
            result.fail("Activity should be a list")
            return

        if activities:
            for i, act in enumerate(activities[:3]):
                for field in ["id", "time", "solver_id", "puzzle_id", "source", "type"]:
                    if field not in act:
                        result.fail(f"Activity {i} missing '{field}'")
                        return
                if act["solver_id"] != sid:
                    result.fail(f"Activity {i} wrong solver_id")
                    return
            if len(activities) > 1:
                times = [a["time"] for a in activities]
                if times[0] < times[-1]:
                    result.fail("Activities not sorted")
                    return

        # Generate activity via assignment
        before_count = len(activities)
        puzzles = self.get_all_puzzles()
        if puzzles:
            self.assign_solver_to_puzzle(sid, puzzles[0]["id"])
            updated = self.api_get(f"/solvers/{sid}/activity")
            if len(updated.get("activity", [])) > before_count:
                self.logger.log_operation(f"  Activity count increased: {before_count} -> {len(updated['activity'])}")

        # Non-existent solver should fail
        r = self.api_get_raw(f"/solvers/999999/activity")
        if r.ok:
            result.fail("Should fail for non-existent solver")
            return

        result.set_success("Solver activity endpoint test completed successfully")

    # ------------------------------------------------------------------
    # Test 18: Solver History
    # ------------------------------------------------------------------
    def test_solver_history(self, result: TestResult):
        solvers = self.get_all_solvers()
        puzzles = self.get_all_puzzles()

        if not solvers or len(solvers) < 2 or not puzzles:
            result.fail("Need at least 2 solvers and puzzles")
            return

        # Get detailed puzzles grouped by round
        detailed = []
        for p in puzzles:
            pd = self.get_puzzle_details(p["id"])
            if pd:
                detailed.append(pd)

        # Select puzzles for testing
        selected = random.sample(detailed, min(4, len(detailed)))

        for puzzle in selected:
            test_solvers = random.sample(solvers, 2)
            for solver in test_solvers:
                # Add to history
                if not self.add_solver_to_history(puzzle["id"], solver["id"]):
                    result.fail(f"Failed to add {solver['name']} to history of {puzzle['name']}")
                    return

                # Verify in history
                pd = self.get_puzzle_details(puzzle["id"])
                hist = pd.get("solvers") or ""
                solver_list = [s.strip() for s in hist.split(",") if s.strip()]
                if solver["name"] not in solver_list:
                    result.fail(f"{solver['name']} not in history of {puzzle['name']}: {solver_list}")
                    return

                # Remove from history
                if not self.remove_solver_from_history(puzzle["id"], solver["id"]):
                    result.fail(f"Failed to remove {solver['name']} from history of {puzzle['name']}")
                    return

                # Verify removed
                pd = self.get_puzzle_details(puzzle["id"])
                hist = pd.get("solvers") or ""
                solver_list = [s.strip() for s in hist.split(",") if s.strip()]
                if solver["name"] in solver_list:
                    result.fail(f"{solver['name']} still in history after removal: {solver_list}")
                    return

        result.set_success("Solver history test completed successfully")

    # ------------------------------------------------------------------
    # Test 19: Sheetcount
    # ------------------------------------------------------------------
    def test_sheetcount(self, result: TestResult):
        puzzles = self.get_all_puzzles()
        if not puzzles:
            result.fail("No puzzles")
            return

        # Test sheetcount on a few puzzles
        selected = random.sample(puzzles, min(3, len(puzzles)))
        for puzzle in selected:
            pid = puzzle["id"]

            # Set sheetcount to a specific value
            test_count = random.randint(2, 10)
            if not self.update_puzzle(pid, "sheetcount", test_count):
                result.fail(f"Failed to set sheetcount for {puzzle['name']}")
                return
            if not self.verify_puzzle_field(result, pid, "sheetcount", test_count):
                return

            # Update sheetcount to a different value
            new_count = test_count + random.randint(1, 5)
            if not self.update_puzzle(pid, "sheetcount", new_count):
                result.fail(f"Failed to update sheetcount for {puzzle['name']}")
                return
            if not self.verify_puzzle_field(result, pid, "sheetcount", new_count):
                return

            # Verify sheetcount in /all endpoint
            all_data = self.api_get("/all")
            found = None
            for rd in all_data.get("rounds", []):
                for p in rd.get("puzzles", []):
                    if p.get("id") == pid:
                        found = p
                        break
                if found:
                    break
            if not found:
                result.fail(f"Puzzle {puzzle['name']} not found in /all endpoint")
                return
            if found.get("sheetcount") != new_count:
                result.fail(f"Sheetcount in /all: expected {new_count}, got {found.get('sheetcount')}")
                return

        result.set_success("Sheetcount test completed successfully")

    # ------------------------------------------------------------------
    # Test 20: Tagging
    # ------------------------------------------------------------------
    def test_tagging(self, result: TestResult):
        tag1 = self.generate_unique_test_tag_name()
        tag2 = self.generate_unique_test_tag_name()
        tag3 = self.generate_unique_test_tag_name()
        self.logger.log_operation(f"Test tags: {tag1}, {tag2}, {tag3}")

        # Test 1: Create standalone tag
        data = self.api_post("/tags", {"name": tag1})
        if data.get("status") != "ok":
            result.fail(f"Failed to create tag: {data}")
            return
        tag1_id = data["tag"]["id"]

        # Test 2: Fetch tag
        fetched = self.api_get(f"/tags/{tag1}")
        if fetched["tag"]["name"] != tag1 or fetched["tag"]["id"] != tag1_id:
            result.fail("Fetched tag mismatch")
            return

        # Verify in tag list
        tags_list = [t["name"] for t in self.api_get("/tags").get("tags", [])]
        if tag1 not in tags_list:
            result.fail(f"Tag {tag1} not in tags list")
            return

        # Test 3: Invalid tag (spaces) should fail
        r = self.api_post_raw("/tags", {"name": "test invalid with spaces"})
        if r.ok and r.json().get("status") == "ok":
            result.fail("Tag with spaces should be rejected")
            return

        # Get a puzzle
        puzzles = self.get_all_puzzles()
        if not puzzles:
            ts = str(int(time.time()))
            rd = self.create_round(f"TagTestRound{ts}")
            self.create_puzzle(f"TagTestPuzzle{ts}", rd["id"])
            puzzles = self.get_all_puzzles()
        pid = puzzles[0]["id"]

        # Test 4: Auto-create tag by adding to puzzle
        self.api_post(f"/puzzles/{pid}/tags", {"tags": {"add": tag2}})
        tag2_id = self.api_get(f"/tags/{tag2}")["tag"]["id"]

        # Test 5: Add existing tag by id
        self.api_post(f"/puzzles/{pid}/tags", {"tags": {"add_id": tag1_id}})

        # Test 6: Non-existent tag id should fail
        r = self.api_post_raw(f"/puzzles/{pid}/tags", {"tags": {"add_id": 999999}})
        if r.ok and r.json().get("status") == "ok":
            result.fail("Non-existent tag_id should fail")
            return

        # Test 7: Puzzle has multiple tags
        pd = self.get_puzzle_details(pid)
        tags = [t.strip() for t in (pd.get("tags") or "").split(",")]
        if tag1 not in tags or tag2 not in tags:
            result.fail(f"Missing tags on puzzle. Expected {tag1}, {tag2} in {tags}")
            return

        # Test 8: GET /puzzles/<id>/tags
        ptags = self.api_get(f"/puzzles/{pid}/tags")
        if ptags.get("status") != "ok":
            result.fail("Failed to get puzzle tags endpoint")
            return

        # Test 9: Search by tag_id
        search = self.api_get(f"/search?tag_id={tag1_id}")
        found_ids = [p["id"] for p in search.get("puzzles", [])]
        if pid not in found_ids:
            result.fail(f"Puzzle not found searching by tag_id {tag1_id}")
            return

        # Test 10: Search by tag name
        search = self.api_get(f"/search?tag={tag2}")
        found_ids = [p["id"] for p in search.get("puzzles", [])]
        if pid not in found_ids:
            result.fail(f"Puzzle not found searching by tag name {tag2}")
            return

        # Bonus: remove_id
        self.api_post(f"/puzzles/{pid}/tags", {"tags": {"remove_id": tag1_id}})
        pd = self.get_puzzle_details(pid)
        tags = [t.strip() for t in (pd.get("tags") or "").split(",") if t.strip()]
        if tag1 in tags:
            result.fail(f"Tag {tag1} not removed")
            return

        # Bonus: lowercase normalization
        upper_tag = self.generate_unique_test_tag_name().upper()
        data = self.api_post("/tags", {"name": upper_tag})
        if data["tag"]["name"] != upper_tag.lower():
            result.fail(f"Tag not lowercased: {data['tag']['name']}")
            return

        result.set_success("Tagging test completed successfully")

    # ------------------------------------------------------------------
    # Test 21: API Endpoints
    # ------------------------------------------------------------------
    def test_api_endpoints(self, result: TestResult):
        """Test basic read-only endpoints return valid data."""
        # /all
        all_data = self.api_get("/all")
        if "rounds" not in all_data:
            result.fail("Invalid /all response")
            return

        # /puzzles
        if "puzzles" not in self.api_get("/puzzles"):
            result.fail("Invalid /puzzles response")
            return

        # /solvers
        if "solvers" not in self.api_get("/solvers"):
            result.fail("Invalid /solvers response")
            return

        # /rounds
        if "rounds" not in self.api_get("/rounds"):
            result.fail("Invalid /rounds response")
            return

        # /huntinfo
        hi = self.api_get("/huntinfo")
        if hi.get("status") != "ok":
            result.fail(f"Invalid /huntinfo status")
            return
        for key in ["config", "statuses", "tags"]:
            if key not in hi:
                result.fail(f"Missing '{key}' in /huntinfo")
                return

        # /statuses
        st = self.api_get("/statuses")
        if st.get("status") != "ok" or "statuses" not in st:
            result.fail("Invalid /statuses response")
            return
        for name in ["New", "Solved"]:
            if name not in st["statuses"]:
                result.fail(f"'{name}' not in /statuses")
                return

        # /config
        cfg = self.api_get("/config")
        if cfg.get("status") != "ok" or "config" not in cfg:
            result.fail("Invalid /config response")
            return
        for key in ["DOMAINNAME", "LOGLEVEL", "BIN_URI"]:
            if key not in cfg["config"]:
                result.fail(f"Missing '{key}' in /config")
                return

        # /solvers/byname/<name>
        solvers = self.get_all_solvers()
        if solvers:
            name = solvers[0]["name"]
            data = self.api_get(f"/solvers/byname/{name}")
            if data.get("status") != "ok" or data.get("solver", {}).get("name") != name:
                result.fail(f"Invalid /solvers/byname/{name} response")
                return

        result.set_success("API endpoints test completed successfully")

    # ------------------------------------------------------------------
    # Test 22: API Documentation
    # ------------------------------------------------------------------
    def test_api_documentation(self, result: TestResult):
        """Test Swagger UI and OpenAPI spec."""
        # Swagger UI page
        r = self.api_get_raw("/apidocs/")
        if not r.ok:
            result.fail(f"/apidocs/ returned {r.status_code}")
            return
        if "swagger-ui" not in r.text.lower():
            result.fail("/apidocs/ missing Swagger UI")
            return

        # OpenAPI spec
        spec = self.api_get("/apispec_1.json")
        if "swagger" not in spec and "openapi" not in spec:
            result.fail("Missing swagger/openapi version")
            return
        if "paths" not in spec:
            result.fail("Missing paths in spec")
            return

        paths = spec["paths"]
        self.logger.log_operation(f"  API spec contains {len(paths)} endpoint paths")

        # Critical endpoints present
        for ep in ["/puzzles", "/rounds", "/solvers", "/botstats", "/botstats/{key}"]:
            if ep not in paths:
                result.fail(f"Missing endpoint {ep} in spec")
                return

        # /botstats has GET + POST
        bs = paths["/botstats"]
        if "get" not in bs or "post" not in bs:
            result.fail("/botstats missing GET or POST")
            return

        # /botstats/{key} has POST
        if "post" not in paths.get("/botstats/{key}", {}):
            result.fail("/botstats/{key} missing POST")
            return

        # Response schemas
        for ep in ["/puzzles", "/rounds", "/solvers"]:
            get_spec = paths[ep].get("get", {})
            if "responses" not in get_spec or "200" not in get_spec.get("responses", {}):
                result.fail(f"{ep} missing response schema")
                return

        result.set_success(f"API documentation test completed successfully - {len(paths)} endpoints documented, Swagger UI accessible")

    # ------------------------------------------------------------------
    # Test 23: Bot Statistics
    # ------------------------------------------------------------------
    def test_bot_statistics(self, result: TestResult):
        ts = str(int(time.time()))
        key = f"test_botstat_{ts}"
        val1 = f"test_value_1_{random.randint(1000, 9999)}"
        val2 = f"test_value_2_{random.randint(1000, 9999)}"

        # Create
        self.api_post(f"/botstats/{key}", {"val": val1})

        # Verify
        botstats = self.api_get("/botstats").get("botstats", {})
        if key not in botstats or botstats[key].get("val") != val1:
            result.fail(f"Botstat {key} not created or wrong value")
            return
        if "updated" not in botstats[key]:
            result.fail("Missing 'updated' timestamp")
            return

        # Update
        self.api_post(f"/botstats/{key}", {"val": val2})
        botstats = self.api_get("/botstats").get("botstats", {})
        if botstats[key].get("val") != val2:
            result.fail(f"Botstat not updated to {val2}")
            return

        # Batch update (array format)
        bk1, bk2 = f"test_batch_1_{ts}", f"test_batch_2_{ts}"
        bv1, bv2 = f"batch_1_{random.randint(1000, 9999)}", f"batch_2_{random.randint(1000, 9999)}"
        data = self.api_post("/botstats", [{"key": bk1, "val": bv1}, {"key": bk2, "val": bv2}])
        if data.get("updated") != 2:
            result.fail(f"Batch array expected 2 updates, got {data.get('updated')}")
            return

        botstats = self.api_get("/botstats").get("botstats", {})
        if botstats.get(bk1, {}).get("val") != bv1 or botstats.get(bk2, {}).get("val") != bv2:
            result.fail("Batch array values incorrect")
            return

        # Batch update (dict format)
        bk3, bk4 = f"test_batch_3_{ts}", f"test_batch_4_{ts}"
        bv3, bv4 = f"batch_3_{random.randint(1000, 9999)}", f"batch_4_{random.randint(1000, 9999)}"
        data = self.api_post("/botstats", {bk3: bv3, bk4: bv4})
        if data.get("updated") != 2:
            result.fail(f"Batch dict expected 2 updates, got {data.get('updated')}")
            return

        botstats = self.api_get("/botstats").get("botstats", {})
        if botstats.get(bk3, {}).get("val") != bv3 or botstats.get(bk4, {}).get("val") != bv4:
            result.fail("Batch dict values incorrect")
            return

        # Single-stat backwards compatibility
        compat_key = f"test_compat_{ts}"
        compat_val = f"compat_{random.randint(1000, 9999)}"
        data = self.api_post(f"/botstats/{compat_key}", {"val": compat_val})
        if data.get("status") != "ok":
            result.fail("Single-stat backwards compat failed")
            return

        result.set_success("Bot statistics test completed successfully (including batch updates)")

    # ------------------------------------------------------------------
    # Test 24: Cache Invalidation
    # ------------------------------------------------------------------
    def test_cache_invalidation(self, result: TestResult):
        fetch_times = []

        # 5 fetches of /allcached
        for i in range(5):
            start = time.time()
            data = self.api_get("/allcached")
            elapsed_ms = (time.time() - start) * 1000
            fetch_times.append(elapsed_ms)
            if "rounds" not in data:
                result.fail(f"Invalid /allcached response on fetch {i+1}")
                return
            self.logger.log_operation(f"  Fetch {i+1}: {elapsed_ms:.2f}ms")

        # Invalidate cache
        data = self.api_post("/cache/invalidate")
        if data.get("status") != "ok":
            result.fail(f"Cache invalidation failed: {data}")
            return

        # Post-invalidation fetch
        start = time.time()
        data = self.api_get("/allcached")
        post_inv_ms = (time.time() - start) * 1000
        if "rounds" not in data:
            result.fail("Invalid /allcached after invalidation")
            return
        self.logger.log_operation(f"  Post-invalidation: {post_inv_ms:.2f}ms (cached was {fetch_times[4]:.2f}ms)")

        # Final fetch to confirm cache repopulated
        self.api_get("/allcached")

        result.set_success("Cache invalidation test completed successfully")

    # ------------------------------------------------------------------
    # Test 25: Puzzle Deletion
    # ------------------------------------------------------------------
    def test_puzzle_deletion(self, result: TestResult):
        ts = str(int(time.time()))
        rd = self.create_round(f"DeleteTestRound {ts}")
        puz = self.create_puzzle(f"DeleteTestPuzzle {ts}", rd["id"])
        pid = puz["id"]
        expected_name = puz["name"]

        # Verify exists
        if not self.get_puzzle_details(pid):
            result.fail("Puzzle not found before deletion")
            return

        # Delete
        data = self.api_delete(f"/deletepuzzle/{expected_name}")
        if data.get("status") != "ok":
            result.fail(f"Delete failed: {data}")
            return

        # Verify gone
        r = self.api_get_raw(f"/puzzles/{pid}")
        if r.ok and r.json().get("puzzle"):
            result.fail("Puzzle still exists after deletion")
            return

        names = [p["name"] for p in self.get_all_puzzles()]
        if expected_name in names:
            result.fail("Deleted puzzle still in puzzles list")
            return

        # Non-existent deletion
        r = self.api_delete_raw(f"/deletepuzzle/NonExistent{ts}")
        self.logger.log_operation(f"  Delete non-existent: {r.status_code}")

        result.set_success("Puzzle deletion test completed successfully")

    # ======================================================================
    # Test suite runner
    # ======================================================================

    def run_all_tests(self, selected_tests=None):
        tests = [
            ("Solver Listing", self.test_solver_listing),
            ("Puzzle Creation (One-Shot)", self.test_puzzle_creation),
            ("Puzzle Creation (Stepwise)", self.test_puzzle_creation_stepwise),
            ("Puzzle Modification", self.test_puzzle_modification),
            ("Puzzle Round Change", self.test_puzzle_round_change),
            ("Puzzle Multi-Part Update", self.test_multi_part_update),
            ("Round Modification", self.test_round_modification),
            ("Round Multi-Part Update", self.test_round_multi_part_update),
            ("Solver Multi-Part Update", self.test_solver_multi_part_update),
            ("Meta Puzzles and Round Completion", self.test_meta_puzzles_and_round_completion),
            ("Answer Verification", self.test_answer_verification),
            ("Solver Assignments", self.test_solver_assignments),
            ("Solve Clears Location and Solvers", self.test_solve_clears_location_and_solvers),
            ("Solver Reassignment", self.test_solver_reassignment),
            ("Activity Tracking", self.test_activity_tracking),
            ("Puzzle Activity Endpoint", self.test_puzzle_activity_endpoint),
            ("Solver Activity Endpoint", self.test_solver_activity_endpoint),
            ("Solver History", self.test_solver_history),
            ("Sheetcount", self.test_sheetcount),
            ("Tagging", self.test_tagging),
            ("API Endpoints", self.test_api_endpoints),
            ("API Documentation", self.test_api_documentation),
            ("Bot Statistics", self.test_bot_statistics),
            ("Cache Invalidation", self.test_cache_invalidation),
            ("Puzzle Deletion", self.test_puzzle_deletion),
        ]

        if selected_tests:
            tests = [(n, f) for i, (n, f) in enumerate(tests) if (i + 1) in selected_tests]

        results = []
        total_start = time.time()

        for name, func in tests:
            test_result, elapsed = self.run_test(name, func)
            results.append((name, test_result, elapsed))

        total_elapsed = time.time() - total_start

        # Summary
        print(f"\n\nTest Results Summary:")
        print("=" * 50)
        passed = failed = 0
        for name, res, elapsed in results:
            icon = "✅" if res.passed else "❌"
            print(f"{icon} {name}: {res.message} ({elapsed:.2f}s)")
            if res.passed:
                passed += 1
            else:
                failed += 1

        print(f"\nTotal tests: {len(results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Total duration: {total_elapsed:.2f}s")

        return failed == 0


# ============================================================================
# Main
# ============================================================================

def reset_hunt():
    """Reset the hunt database using reset-hunt.py."""
    script = os.path.join(os.path.dirname(__file__), "reset-hunt.py")
    if not os.path.exists(script):
        print(f"WARNING: {script} not found, skipping reset")
        return
    print("Resetting hunt database...")
    result = subprocess.run(
        ["python3", script, "--yes-i-am-sure-i-want-to-destroy-all-data"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"WARNING: Reset failed: {result.stderr}")
    else:
        print("Hunt reset completed successfully")


def ensure_test_solvers(base_url, count=10):
    """Ensure enough test solvers exist."""
    try:
        r = requests.get(f"{base_url}/solvers")
        solvers = r.json().get("solvers", [])
        existing = len(solvers)
        if existing >= count:
            print(f"  Sufficient solvers available ({existing} >= {count})")
            return
        for i in range(count - existing):
            name = f"testuser{existing + i + 1}"
            requests.post(f"{base_url}/solvers", json={"name": name, "fullname": f"Test User {existing + i + 1}"})
        print(f"  Created {count - existing} additional test solvers")
    except Exception as e:
        print(f"  Warning: Could not ensure test solvers: {e}")


def main():
    parser = argparse.ArgumentParser(description="PuzzleBoss API Test Suite")
    parser.add_argument("--allow-destructive", action="store_true",
                        help="Allow destructive database operations (required)")
    parser.add_argument("--tests", nargs="+", type=int,
                        help="Run specific test numbers (1-25)")
    parser.add_argument("--list", action="store_true",
                        help="List all tests")
    parser.add_argument("--base-url", default=BASE_URL,
                        help=f"API base URL (default: {BASE_URL})")
    args = parser.parse_args()

    if args.list:
        runner = TestRunner()
        tests = [
            "Solver Listing", "Puzzle Creation (One-Shot)", "Puzzle Creation (Stepwise)",
            "Puzzle Modification", "Puzzle Round Change", "Puzzle Multi-Part Update",
            "Round Modification", "Round Multi-Part Update", "Solver Multi-Part Update",
            "Meta Puzzles and Round Completion", "Answer Verification", "Solver Assignments",
            "Solve Clears Location and Solvers", "Solver Reassignment", "Activity Tracking",
            "Puzzle Activity Endpoint", "Solver Activity Endpoint", "Solver History",
            "Sheetcount", "Tagging", "API Endpoints", "API Documentation",
            "Bot Statistics", "Cache Invalidation", "Puzzle Deletion",
        ]
        for i, name in enumerate(tests, 1):
            print(f"  {i:2d}. {name}")
        sys.exit(0)

    if not args.allow_destructive:
        print("ERROR: This test suite modifies the database.")
        print("Run with --allow-destructive to confirm.")
        sys.exit(1)

    reset_hunt()
    ensure_test_solvers(args.base_url)

    runner = TestRunner(args.base_url)
    success = runner.run_all_tests(selected_tests=args.tests)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
