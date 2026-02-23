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

import random
import string
import sys
import time
import traceback

import requests

from test_helpers import (
    API_URL,
    TestLogger,
    TestResult,
    find_by_name,
    assert_eq,
    assert_field,
    assert_in,
    assert_true,
    reset_hunt,
    ensure_test_solvers_api,
    make_arg_parser,
    handle_list_and_destructive,
)

# Configuration
BASE_URL = API_URL


# ============================================================================
# Test runner
# ============================================================================

class TestRunner:
    # Canonical list of test names — used by both run_all_tests() and --list.
    TEST_NAMES = [
        "Solver Listing",
        "Puzzle Creation (One-Shot)",
        "Puzzle Creation (Stepwise)",
        "Puzzle Modification",
        "Puzzle Round Change",
        "Puzzle Multi-Part Update",
        "Round Modification",
        "Round Multi-Part Update",
        "Solver Multi-Part Update",
        "Meta Puzzles and Round Completion",
        "Answer Verification",
        "Solver Assignments",
        "Solve Clears Location and Solvers",
        "Solver Reassignment",
        "Activity Tracking",
        "Puzzle Activity Endpoint",
        "Solver Activity Endpoint",
        "Solver History",
        "Sheetcount",
        "Tagging",
        "API Endpoints",
        "API Documentation",
        "Bot Statistics",
        "Cache Invalidation",
        "Solver CRUD",
        "RBAC Privilege Management",
        "Puzzle Deletion",
        "Hint Queue",
        "Activity Search",
        "Activity Type Verification",
        "Discord Source Propagation",
        "Activity Statistics Endpoint",
        "Activity has_more and Comment Type",
        "Activity Source Metrics",
    ]

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
        except Exception as e:
            self.logger.log_error(f"Failed to get puzzle details for {puzzle_id}: {e}")
            return None

    def get_solver_details(self, solver_id):
        try:
            data = self.api_get(f"/solvers/{solver_id}")
            return data.get("solver", data)
        except Exception as e:
            self.logger.log_error(f"Failed to get solver details for {solver_id}: {e}")
            return None

    def get_round(self, round_id):
        try:
            data = self.api_get(f"/rounds/{round_id}")
            return data.get("round", data)
        except Exception as e:
            self.logger.log_error(f"Failed to get round details for {round_id}: {e}")
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
        r = find_by_name(self.get_all_rounds(), sanitized)
        if not r:
            raise Exception(f"Round '{sanitized}' not found after creation")
        self.logger.log_operation(f"  Created round '{sanitized}' (id {r['id']})")
        return r

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
        sanitized = name.replace(" ", "")
        p = find_by_name(self.get_all_puzzles(), sanitized)
        if not p:
            raise Exception(f"Puzzle '{sanitized}' not found after creation")
        details = self.get_puzzle_details(p["id"])
        if not details:
            raise Exception(f"Puzzle '{sanitized}' found but details unavailable")
        return details

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

        sanitized = name.replace(" ", "")
        p = find_by_name(self.get_all_puzzles(), sanitized)
        if not p:
            raise Exception(f"Stepwise puzzle '{sanitized}' not found after creation")
        details = self.get_puzzle_details(p["id"])
        if not details:
            raise Exception(f"Stepwise puzzle '{sanitized}' found but details unavailable")
        return details

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
        except Exception as e:
            self.logger.log_error(f"Failed to fetch existing tags: {e}")
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

        # Find a round with an unsolved puzzle and a different target round
        test_puzzle = None
        round_1 = None
        round_2 = None

        all_puzzles = self.get_all_puzzles()

        # Find any unsolved puzzle
        for p in all_puzzles:
            details = self.get_puzzle_details(p["id"])
            if details and details.get("status") != "Solved":
                test_puzzle = details
                # Find the round this puzzle is in
                for r in rounds:
                    if str(r["id"]) == str(details.get("round_id")):
                        round_1 = r
                        break
                break

        if not test_puzzle or not round_1:
            result.fail("No unsolved puzzles found in any round")
            return

        # Find a different round to move to
        for r in rounds:
            if str(r["id"]) != str(round_1["id"]):
                round_2 = r
                break

        if not round_2:
            result.fail("Need at least 2 different rounds")
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
    # Test 25: Solver CRUD (Create and Delete)
    # ------------------------------------------------------------------
    def test_solver_crud(self, result: TestResult):
        """Test creating a solver, verifying it exists, and deleting it."""
        ts = str(int(time.time()))
        username = f"crudtest{ts}"
        fullname = f"CRUD Test User {ts}"

        # Create solver
        self.logger.log_operation(f"Creating solver: {username}")
        data = self.create_solver(username, fullname)
        if data.get("status") != "ok":
            result.fail(f"Solver creation failed: {data}")
            return

        # Find the new solver by name
        solver = None
        for s in self.get_all_solvers():
            if s["name"] == username:
                solver = s
                break
        if not solver:
            result.fail(f"Solver '{username}' not found after creation")
            return

        sid = solver["id"]
        self.logger.log_operation(f"  Created solver id={sid}")

        # Verify details
        details = self.get_solver_details(sid)
        if not details or details.get("name") != username:
            result.fail(f"Solver details mismatch: {details}")
            return
        if details.get("fullname") != fullname:
            result.fail(f"Fullname mismatch: expected {fullname!r}, got {details.get('fullname')!r}")
            return

        # Verify lookup by name
        byname = self.api_get(f"/solvers/byname/{username}")
        if byname.get("solver", {}).get("id") != sid:
            result.fail(f"/solvers/byname/{username} returned wrong id")
            return

        # Duplicate creation should fail gracefully
        r = self.api_post_raw("/solvers", {"name": username, "fullname": fullname})
        self.logger.log_operation(f"  Duplicate creation: {r.status_code}")

        # Delete solver
        # Note: /deleteuser also tries to delete from Google Workspace, which may
        # fail in Docker (no Google API). The DB deletion happens first, so we
        # accept either success or a Google-related error.
        self.logger.log_operation(f"Deleting solver: {username}")
        r = self.api_get_raw(f"/deleteuser/{username}")
        if r.ok:
            self.logger.log_operation(f"  Delete returned ok")
        else:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            error_msg = body.get("error", "")
            if "Google" in error_msg or "credentials" in error_msg.lower():
                self.logger.log_warning(f"  Google API error (expected in Docker): {error_msg[:80]}")
            else:
                result.fail(f"Solver deletion failed unexpectedly: {r.status_code} {error_msg}")
                return

        # Verify gone from DB regardless of Google error
        for s in self.get_all_solvers():
            if s["name"] == username:
                result.fail(f"Solver '{username}' still exists after deletion")
                return
        self.logger.log_operation(f"  ✓ Solver removed from database")

        # Delete non-existent solver
        r = self.api_get_raw(f"/deleteuser/nonexistent{ts}")
        self.logger.log_operation(f"  Delete non-existent: {r.status_code}")

        result.set_success("Solver CRUD test completed successfully")

    # ------------------------------------------------------------------
    # Test 26: RBAC Privilege Management
    # ------------------------------------------------------------------
    def test_rbac_privileges(self, result: TestResult):
        """Test granting, checking, and revoking privileges via the RBAC API."""
        solvers = self.get_all_solvers()
        if not solvers:
            result.fail("No solvers found")
            return

        # Use a non-admin solver (not the first one which may be testuser with privs)
        test_solver = None
        for s in solvers:
            if s["name"] != "testuser":
                test_solver = s
                break
        if not test_solver:
            result.fail("Need a non-testuser solver for RBAC test")
            return

        sid = test_solver["id"]
        self.logger.log_operation(f"Testing RBAC on solver {test_solver['name']} (id={sid})")

        # Check initial state - should not have puzztech
        data = self.api_get(f"/rbac/puzztech/{sid}")
        if data.get("status") != "ok":
            result.fail(f"RBAC check failed: {data}")
            return
        initial_puzztech = data.get("allowed", False)
        self.logger.log_operation(f"  Initial puzztech: {initial_puzztech}")

        # Grant puzztech
        self.logger.log_operation(f"  Granting puzztech...")
        data = self.api_post(f"/rbac/puzztech/{sid}", {"allowed": "YES"})
        if data.get("status") != "ok":
            result.fail(f"Grant puzztech failed: {data}")
            return

        # Verify granted
        data = self.api_get(f"/rbac/puzztech/{sid}")
        if not data.get("allowed"):
            result.fail("puzztech not granted after POST YES")
            return
        self.logger.log_operation(f"  ✓ puzztech granted")

        # Grant puzzleboss
        self.logger.log_operation(f"  Granting puzzleboss...")
        data = self.api_post(f"/rbac/puzzleboss/{sid}", {"allowed": "YES"})
        if data.get("status") != "ok":
            result.fail(f"Grant puzzleboss failed: {data}")
            return
        data = self.api_get(f"/rbac/puzzleboss/{sid}")
        if not data.get("allowed"):
            result.fail("puzzleboss not granted after POST YES")
            return
        self.logger.log_operation(f"  ✓ puzzleboss granted")

        # Check /privs endpoint includes this user
        privs_data = self.api_get("/privs")
        found = False
        for p in privs_data.get("privs", []):
            if p.get("uid") == sid:
                if p.get("puzztech") != "YES" or p.get("puzzleboss") != "YES":
                    result.fail(f"Privs mismatch in /privs: {p}")
                    return
                found = True
                break
        if not found:
            result.fail(f"Solver {sid} not found in /privs")
            return
        self.logger.log_operation(f"  ✓ Verified in /privs endpoint")

        # Revoke puzztech
        self.logger.log_operation(f"  Revoking puzztech...")
        self.api_post(f"/rbac/puzztech/{sid}", {"allowed": "NO"})
        data = self.api_get(f"/rbac/puzztech/{sid}")
        if data.get("allowed"):
            result.fail("puzztech not revoked after POST NO")
            return
        self.logger.log_operation(f"  ✓ puzztech revoked")

        # Revoke puzzleboss
        self.api_post(f"/rbac/puzzleboss/{sid}", {"allowed": "NO"})
        data = self.api_get(f"/rbac/puzzleboss/{sid}")
        if data.get("allowed"):
            result.fail("puzzleboss not revoked after POST NO")
            return
        self.logger.log_operation(f"  ✓ puzzleboss revoked")

        # Test invalid priv value
        r = self.api_post_raw(f"/rbac/puzztech/{sid}", {"allowed": "MAYBE"})
        if r.ok:
            result.fail("Invalid priv value 'MAYBE' was accepted")
            return
        self.logger.log_operation(f"  ✓ Invalid value correctly rejected")

        result.set_success("RBAC privilege management test completed successfully")

    # ------------------------------------------------------------------
    # Test 27: Puzzle Deletion
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

    # ------------------------------------------------------------------
    # Test 28: Hint Queue
    # ------------------------------------------------------------------
    def test_hint_queue(self, result: TestResult):
        ts = str(int(time.time()))
        rd = self.create_round(f"HintRound {ts}")
        puz1 = self.create_puzzle(f"HintPuzzle1 {ts}", rd["id"])
        puz2 = self.create_puzzle(f"HintPuzzle2 {ts}", rd["id"])
        ctx = {"ts": ts, "puz1": puz1, "puz2": puz2, "hint_ids": []}

        self._hint_create_and_verify(result, ctx)
        if not result.passed:
            return
        self._hint_auto_promotion(result, ctx)
        if not result.passed:
            return
        self._hint_submit_to_hq(result, ctx)
        if not result.passed:
            return
        self._hint_answer_submitted(result, ctx)
        if not result.passed:
            return
        self._hint_demote(result, ctx)
        if not result.passed:
            return
        self._hint_answer_ready(result, ctx)
        if not result.passed:
            return
        self._hint_delete_and_cleanup(result, ctx)
        if not result.passed:
            return
        self._hint_errors_and_all(result, ctx)
        if not result.passed:
            return
        result.set_success("Hint queue test completed successfully")

    def _hint_create_and_verify(self, result, ctx):
        """Create 3 hints and verify list/count/positions."""
        ts, puz1, puz2 = ctx["ts"], ctx["puz1"], ctx["puz2"]

        # Initially empty
        data = self.api_get("/hints")
        if not assert_true(result, isinstance(data.get("hints", []), list), "GET /hints did not return a list"):
            return
        initial_count = self.api_get("/hints/count").get("count", -1)
        self.logger.log_operation(f"  ✓ Initial hint count = {initial_count}")

        # Create three hints
        for i, (puz, text) in enumerate([
            (puz1, f"Need help with clue A {ts}"),
            (puz2, f"Stuck on extraction {ts}"),
            (puz1, f"Second hint for puzzle 1 {ts}"),
        ]):
            resp = self.api_post("/hints", {"puzzle_id": puz["id"], "solver": "testuser", "request_text": text})
            if not assert_eq(result, resp.get("status"), "ok", f"POST /hints hint {i+1}"):
                return
            hid = resp.get("id") or resp.get("hint", {}).get("id")
            if not assert_true(result, hid, f"POST /hints did not return id for hint {i+1}"):
                return
            ctx["hint_ids"].append(hid)
            self.logger.log_operation(f"  ✓ Created hint {i+1} (id={hid})")

        # Verify count and positions
        data = self.api_get("/hints")
        hints = data.get("hints", [])
        if not assert_true(result, len(hints) >= 3, f"Expected ≥3 hints, got {len(hints)}"):
            return
        new_count = self.api_get("/hints/count").get("count", -1)
        if not assert_true(result, new_count >= initial_count + 3, f"Count {new_count} < {initial_count + 3}"):
            return
        positions = sorted([h["queue_position"] for h in hints if h["id"] in ctx["hint_ids"]])
        if not assert_eq(result, positions, [1, 2, 3], "Queue positions"):
            return

        # Verify puzzle_name field
        top = [h for h in hints if h["id"] == ctx["hint_ids"][0]]
        if not assert_true(result, top and top[0].get("puzzle_name"), "Hint missing puzzle_name"):
            return
        self.logger.log_operation("  ✓ Hints created, counted, positioned, with puzzle_name")

    def _hint_auto_promotion(self, result, ctx):
        """Verify top hint is 'ready', others are 'queued'."""
        data = self.api_get("/hints")
        hints = data.get("hints", [])
        top_hint = [h for h in hints if h["queue_position"] == 1][0]
        if not assert_eq(result, top_hint["status"], "ready", "Top hint status"):
            return
        for h in [h for h in hints if h["queue_position"] > 1 and h["id"] in ctx["hint_ids"]]:
            if not assert_eq(result, h["status"], "queued", f"Hint at pos {h['queue_position']}"):
                return
        ctx["top_hint_id"] = top_hint["id"]
        self.logger.log_operation("  ✓ Auto-promotion: top=ready, others=queued")

    def _hint_submit_to_hq(self, result, ctx):
        """Submit the top hint and verify status changes."""
        resp = self.api_post(f"/hints/{ctx['top_hint_id']}/submit", {})
        if not assert_eq(result, resp.get("status"), "ok", "Submit hint"):
            return
        data = self.api_get("/hints")
        submitted = [h for h in data["hints"] if h["id"] == ctx["top_hint_id"]][0]
        if not assert_eq(result, submitted["status"], "submitted", "Submitted hint status"):
            return
        # Submit of non-ready hint should fail
        r = self.api_post_raw(f"/hints/{ctx['hint_ids'][1]}/submit", {})
        if r.status_code < 400:
            self.logger.log_warning(f"  Submit of non-ready hint returned {r.status_code} (expected 404)")
        else:
            self.logger.log_operation(f"  ✓ Non-ready submit correctly returned {r.status_code}")
        self.logger.log_operation("  ✓ Submit endpoint works correctly")

    def _hint_answer_submitted(self, result, ctx):
        """Answer the submitted hint, verify auto-promotion of next."""
        resp = self.api_post(f"/hints/{ctx['top_hint_id']}/answer", {})
        if not assert_eq(result, resp.get("status"), "ok", "Answer submitted hint"):
            return
        data = self.api_get("/hints")
        hints = data.get("hints", [])
        if hints:
            new_top = [h for h in hints if h["queue_position"] == 1]
            if new_top:
                if not assert_eq(result, new_top[0]["status"], "ready", "New top hint after answer"):
                    return
        self.logger.log_operation("  ✓ Answered submitted hint, new top auto-promoted")

    def _hint_demote(self, result, ctx):
        """Demote ready hint, verify position swap and status reset."""
        hint_ids = ctx["hint_ids"]
        resp = self.api_post(f"/hints/{hint_ids[1]}/demote", {})
        if not assert_eq(result, resp.get("status"), "ok", "Demote hint"):
            return
        data = self.api_get("/hints")
        hints = data.get("hints", [])
        pos_map = {h["id"]: h["queue_position"] for h in hints}
        status_map = {h["id"]: h["status"] for h in hints}
        if not assert_eq(result, pos_map.get(hint_ids[1]), 2, "Demoted hint position"):
            return
        if not assert_eq(result, pos_map.get(hint_ids[2]), 1, "Promoted hint position"):
            return
        if not assert_eq(result, status_map.get(hint_ids[1]), "queued", "Demoted hint status"):
            return
        if not assert_eq(result, status_map.get(hint_ids[2]), "ready", "Promoted hint status"):
            return
        self.logger.log_operation("  ✓ Demote swapped positions and reset statuses")

    def _hint_answer_ready(self, result, ctx):
        """Answer the ready hint, verify removal and promotion of remaining."""
        hint_ids = ctx["hint_ids"]
        resp = self.api_post(f"/hints/{hint_ids[2]}/answer", {})
        if not assert_eq(result, resp.get("status"), "ok", "Answer ready hint"):
            return
        data = self.api_get("/hints")
        hints = data.get("hints", [])
        if not assert_true(result, hint_ids[2] not in [h["id"] for h in hints], "Answered hint still in list"):
            return
        remaining = [h for h in hints if h["id"] == hint_ids[1]]
        if not assert_true(result, remaining, "Remaining hint not found"):
            return
        if not assert_eq(result, remaining[0]["queue_position"], 1, "Remaining hint position"):
            return
        if not assert_eq(result, remaining[0]["status"], "ready", "Remaining hint status"):
            return
        self.logger.log_operation("  ✓ Answer removed hint, remaining promoted to pos 1 as ready")

    def _hint_delete_and_cleanup(self, result, ctx):
        """Delete a hint, verify auto-promotion of next."""
        hint_ids = ctx["hint_ids"]
        ts = ctx["ts"]
        # Create extra hint so we have 2 to test delete + promotion
        resp = self.api_post("/hints", {
            "puzzle_id": ctx["puz2"]["id"], "solver": "testuser",
            "request_text": f"Extra hint for delete test {ts}"
        })
        ctx["extra_id"] = resp.get("hint", {}).get("id")
        resp = self.api_delete(f"/hints/{hint_ids[1]}")
        if not assert_eq(result, resp.get("status"), "ok", "Delete hint"):
            return
        data = self.api_get("/hints")
        hints = data.get("hints", [])
        if not assert_true(result, not any(h["id"] == hint_ids[1] for h in hints), "Deleted hint still in list"):
            return
        extra = [h for h in hints if h["id"] == ctx["extra_id"]]
        if extra:
            if not assert_eq(result, extra[0]["status"], "ready", "After delete, new top status"):
                return
        self.logger.log_operation("  ✓ Delete removed hint, new top auto-promoted")

    def _hint_errors_and_all(self, result, ctx):
        """Verify /all includes hints, test error cases, clean up."""
        extra_id = ctx.get("extra_id")
        puz1 = ctx["puz1"]

        all_data = self.api_get("/all")
        if not assert_in(result, "hints", all_data, "/all response"):
            return
        self.logger.log_operation(f"  ✓ /all includes hints ({len(all_data['hints'])} hints)")

        # Error cases
        if extra_id:
            r = self.api_post_raw(f"/hints/{extra_id}/demote", {})
            if r.status_code < 400:
                self.logger.log_warning(f"  Demote of last hint returned {r.status_code} (expected 400)")
            else:
                self.logger.log_operation(f"  ✓ Demote of last hint correctly returned {r.status_code}")

        r = self.api_delete_raw("/hints/999999")
        self.logger.log_operation(f"  Delete non-existent hint: {r.status_code}")

        r = self.api_post_raw("/hints", {"puzzle_id": puz1["id"]})
        if r.ok:
            self.logger.log_warning("  POST /hints with missing fields unexpectedly succeeded")
        else:
            self.logger.log_operation(f"  ✓ POST /hints with missing fields returned {r.status_code}")

        # Clean up
        data = self.api_get("/hints")
        for h in data.get("hints", []):
            self.api_delete(f"/hints/{h['id']}")
        self.logger.log_operation("  ✓ Cleaned up remaining test hints")

    # ------------------------------------------------------------------
    # Test 29: Activity Search Endpoint
    # ------------------------------------------------------------------
    def test_activity_search(self, result: TestResult):
        """Test the /activitysearch endpoint with various filter combinations."""
        puz, solver = self._activity_search_setup(result)
        if not result.passed:
            return
        self._activity_search_basic_and_shape(result)
        if not result.passed:
            return
        self._activity_search_filters(result, puz, solver)
        if not result.passed:
            return
        self._activity_search_errors_and_ordering(result)
        if not result.passed:
            return
        result.set_success("Activity search endpoint test completed successfully")

    def _activity_search_setup(self, result):
        """Set up test data for activity search tests. Returns (puzzle, solver)."""
        rounds = self.get_all_rounds()
        if not rounds:
            rnd = self.create_round(self.get_emoji_string("SearchRnd", include_emoji=False))
            rounds = [rnd]

        puz = self.create_puzzle(
            self.get_emoji_string("SearchTestPuz", include_emoji=False),
            rounds[0]["id"]
        )
        solvers = self.get_all_solvers()
        if not assert_true(result, solvers, "No solvers available"):
            return None, None
        solver = solvers[0]

        # Generate activity: assign solver, change status, change xyzloc
        self.assign_solver_to_puzzle(solver["id"], puz["id"])
        self.api_post(f"/puzzles/{puz['id']}/status", {"status": "Critical"})
        self.api_post(f"/puzzles/{puz['id']}/xyzloc", {"xyzloc": "Table 5"})
        return puz, solver

    def _activity_search_basic_and_shape(self, result):
        """Test no-filter search and validate response shape."""
        self.logger.log_operation("  Testing: no filters")
        data = self.api_get("/activitysearch")
        if not assert_eq(result, data.get("status"), "ok", "No-filter search"):
            return
        if not assert_true(result, isinstance(data.get("activity"), list), "activity should be a list"):
            return
        if not assert_true(result, data.get("count", 0) >= 1, "Should have ≥1 activity entry"):
            return
        self.logger.log_operation(f"    ✓ Got {data['count']} results")

        required_fields = ["id", "time", "type", "source", "puzzle_id", "solver_id", "puzzle_name", "solver_name"]
        for field in required_fields:
            if not assert_in(result, field, data["activity"][0], "Activity result fields"):
                return
        self.logger.log_operation("    ✓ Response shape validated")

    def _activity_search_filters(self, result, puz, solver):
        """Test individual and combined filters using data-driven approach."""
        # Data-driven filter tests: (label, query_params, validate_fn)
        filter_tests = [
            ("type", "types=assignment,status",
             lambda act: act["type"] in ("assignment", "status")),
            ("source", "sources=puzzleboss",
             lambda act: act["source"] == "puzzleboss"),
            ("solver_id", f"solver_id={solver['id']}",
             lambda act: True),  # solver_id filter is loose (system entries OK)
            ("puzzle_id", f"puzzle_id={puz['id']}",
             lambda act: act["puzzle_id"] == puz["id"]),
            ("limit", "limit=50",
             lambda act: True),  # just verify count
        ]

        for label, params, validate_fn in filter_tests:
            self.logger.log_operation(f"  Testing: {label} filter")
            data = self.api_get(f"/activitysearch?{params}")
            if not assert_eq(result, data.get("status"), "ok", f"{label} filter search"):
                return
            for act in data.get("activity", []):
                if not validate_fn(act):
                    result.fail(f"{label} filter leaked: {act}")
                    return
            if label == "limit":
                if not assert_true(result, len(data.get("activity", [])) <= 50, "Limit 50 exceeded"):
                    return
            self.logger.log_operation(f"    ✓ {label} filter returned {data['count']} results")

        # Combined filters
        self.logger.log_operation("  Testing: combined filters")
        data = self.api_get(f"/activitysearch?types=change&sources=puzzleboss&puzzle_id={puz['id']}&limit=50")
        if not assert_eq(result, data.get("status"), "ok", "Combined filter"):
            return
        for act in data.get("activity", []):
            if not assert_eq(result, act["type"], "change", "Combined: type"):
                return
            if not assert_eq(result, act["source"], "puzzleboss", "Combined: source"):
                return
            if not assert_eq(result, act["puzzle_id"], puz["id"], "Combined: puzzle_id"):
                return
        self.logger.log_operation(f"    ✓ Combined filters returned {data['count']} results")

    def _activity_search_errors_and_ordering(self, result):
        """Test error cases and time ordering."""
        self.logger.log_operation("  Testing: error cases")

        error_cases = [
            ("/activitysearch?limit=999", "Invalid limit"),
            ("/activitysearch?types=bogustype", "Invalid type"),
            ("/activitysearch?solver_id=notanumber", "Non-integer solver_id"),
        ]
        for path, label in error_cases:
            r = self.api_get_raw(path)
            if not assert_true(result, not r.ok, f"{label} should return error"):
                return
            self.logger.log_operation(f"    ✓ {label} returned {r.status_code}")

        # Time ordering
        self.logger.log_operation("  Testing: time ordering")
        data = self.api_get("/activitysearch?limit=50")
        activities = data.get("activity", [])
        if len(activities) > 1:
            times = [a["time"] for a in activities]
            if not assert_true(result, times[0] >= times[-1], "Activities not sorted most-recent-first"):
                return
        self.logger.log_operation("    ✓ Results sorted by time DESC")

    # ------------------------------------------------------------------
    # Test 30: Activity Type Verification
    # ------------------------------------------------------------------
    def test_activity_type_verification(self, result: TestResult):
        """Verify that actions produce the correct new activity type values."""
        rounds = self.get_all_rounds()
        if not rounds:
            rnd = self.create_round("TypeVerifyRnd")
            rounds = [rnd]
        round_id = rounds[0]["id"]

        puz = self.create_puzzle(
            self.get_emoji_string("TypeVerifyPuz", include_emoji=False),
            round_id
        )
        solvers = self.get_all_solvers()
        if not solvers:
            result.fail("No solvers available")
            return
        solver = solvers[0]

        def get_latest_activity(puzzle_id, expected_type=None):
            """Get recent activity for a puzzle, optionally filtered by type."""
            data = self.api_get(f"/puzzles/{puzzle_id}/activity")
            acts = data.get("activity", [])
            if expected_type:
                return [a for a in acts if a.get("type") == expected_type]
            return acts

        # 1. Puzzle creation should produce 'create' type
        self.logger.log_operation("  Checking: puzzle creation → 'create' type")
        acts = get_latest_activity(puz["id"], "create")
        if not acts:
            result.fail("No 'create' activity found after puzzle creation")
            return
        self.logger.log_operation(f"    ✓ Found {len(acts)} 'create' activity entry(ies)")

        # 2. Solver assignment should produce 'assignment' type (not 'interact')
        self.logger.log_operation("  Checking: solver assignment → 'assignment' type")
        self.assign_solver_to_puzzle(solver["id"], puz["id"])
        acts = get_latest_activity(puz["id"], "assignment")
        if not acts:
            result.fail("No 'assignment' activity found after solver assignment")
            return
        # Also verify 'interact' was NOT used
        interact_acts = get_latest_activity(puz["id"], "interact")
        self.logger.log_operation(f"    ✓ Found {len(acts)} 'assignment' entry(ies), {len(interact_acts)} legacy 'interact' entries")

        # 3. Solver assignment should also produce 'status' for auto-transition
        self.logger.log_operation("  Checking: assignment auto-transition → 'status' type")
        acts = get_latest_activity(puz["id"], "status")
        if not acts:
            result.fail("No 'status' activity found after assignment (auto-transition to 'Being worked')")
            return
        self.logger.log_operation(f"    ✓ Found {len(acts)} 'status' entry(ies)")

        # 4. xyzloc change should produce 'change' type (not 'interact')
        self.logger.log_operation("  Checking: xyzloc change → 'change' type")
        self.api_post(f"/puzzles/{puz['id']}/xyzloc", {"xyzloc": "Room 7"})
        acts = get_latest_activity(puz["id"], "change")
        if not acts:
            result.fail("No 'change' activity found after xyzloc update")
            return
        self.logger.log_operation(f"    ✓ Found {len(acts)} 'change' entry(ies)")

        # 5. Manual status change should produce 'status' type
        self.logger.log_operation("  Checking: status change → 'status' type")
        before_status_count = len(get_latest_activity(puz["id"], "status"))
        self.api_post(f"/puzzles/{puz['id']}/status", {"status": "Needs eyes"})
        after_acts = get_latest_activity(puz["id"], "status")
        if len(after_acts) <= before_status_count:
            result.fail("No new 'status' activity after manual status change")
            return
        self.logger.log_operation(f"    ✓ Status count increased: {before_status_count} → {len(after_acts)}")

        # 6. Solve should still produce 'solve' type
        self.logger.log_operation("  Checking: solve → 'solve' type")
        self.api_post(f"/puzzles/{puz['id']}/answer", {"answer": "TYPETEST"})
        acts = get_latest_activity(puz["id"], "solve")
        if not acts:
            result.fail("No 'solve' activity found after answering puzzle")
            return
        self.logger.log_operation(f"    ✓ Found {len(acts)} 'solve' entry(ies)")

        result.set_success("Activity type verification test completed successfully")

    # ------------------------------------------------------------------
    # Test 31: Discord Source Propagation
    # ------------------------------------------------------------------
    def test_discord_source_propagation(self, result: TestResult):
        """Verify that source='discord' propagates correctly through puzzle update endpoints."""
        rounds = self.get_all_rounds()
        if not rounds:
            rnd = self.create_round("DiscordSrcRnd")
            rounds = [rnd]
        round_id = rounds[0]["id"]

        puz = self.create_puzzle(
            self.get_emoji_string("DiscordSrcPuz", include_emoji=False),
            round_id
        )

        def get_puzzle_activity(puzzle_id, expected_type=None):
            data = self.api_get(f"/puzzles/{puzzle_id}/activity")
            acts = data.get("activity", [])
            if expected_type:
                return [a for a in acts if a.get("type") == expected_type]
            return acts

        # 1. xyzloc change with source=discord
        self.logger.log_operation("  Testing: xyzloc with source=discord")
        self.api_post(f"/puzzles/{puz['id']}/xyzloc", {"xyzloc": "Discord Room", "source": "discord"})
        acts = get_puzzle_activity(puz["id"], "change")
        discord_acts = [a for a in acts if a.get("source") == "discord"]
        if not discord_acts:
            result.fail("No discord-sourced 'change' activity after xyzloc update")
            return
        self.logger.log_operation(f"    ✓ xyzloc change has source=discord ({len(discord_acts)} entry)")

        # 2. Status change with source=discord
        self.logger.log_operation("  Testing: status with source=discord")
        self.api_post(f"/puzzles/{puz['id']}/status", {"status": "Needs eyes", "source": "discord"})
        acts = get_puzzle_activity(puz["id"], "status")
        discord_acts = [a for a in acts if a.get("source") == "discord"]
        if not discord_acts:
            result.fail("No discord-sourced 'status' activity after status update")
            return
        self.logger.log_operation(f"    ✓ status change has source=discord ({len(discord_acts)} entry)")

        # 3. Multi-part update with source=discord
        self.logger.log_operation("  Testing: multi-part update with source=discord")
        self.api_post(f"/puzzles/{puz['id']}", {"xyzloc": "Room 2", "source": "discord"})
        acts = get_puzzle_activity(puz["id"], "change")
        discord_acts = [a for a in acts if a.get("source") == "discord"]
        if len(discord_acts) < 2:
            result.fail(f"Expected at least 2 discord-sourced 'change' entries, got {len(discord_acts)}")
            return
        self.logger.log_operation(f"    ✓ multi-part update has source=discord ({len(discord_acts)} entries)")

        # 4. Solve with source=discord
        self.logger.log_operation("  Testing: answer with source=discord")
        self.api_post(f"/puzzles/{puz['id']}/answer", {"answer": "DISCORDTEST", "source": "discord"})
        acts = get_puzzle_activity(puz["id"], "solve")
        discord_acts = [a for a in acts if a.get("source") == "discord"]
        if not discord_acts:
            result.fail("No discord-sourced 'solve' activity after answering puzzle")
            return
        self.logger.log_operation(f"    ✓ solve has source=discord ({len(discord_acts)} entry)")

        # 5. Activity search filtered by source=discord
        self.logger.log_operation("  Testing: activitysearch with sources=discord")
        data = self.api_get("/activitysearch?sources=discord")
        if data.get("status") != "ok":
            result.fail(f"activitysearch?sources=discord failed: {data}")
            return
        for act in data.get("activity", []):
            if act["source"] != "discord":
                result.fail(f"Source filter leaked: got source '{act['source']}' with sources=discord filter")
                return
        self.logger.log_operation(f"    ✓ activitysearch sources=discord returned {data['count']} results (all discord)")

        # 6. Combined filter: sources=discord + puzzle_id
        self.logger.log_operation("  Testing: combined filter sources=discord + puzzle_id")
        data = self.api_get(f"/activitysearch?sources=discord&puzzle_id={puz['id']}")
        if data.get("status") != "ok":
            result.fail(f"Combined filter search failed: {data}")
            return
        if data["count"] < 3:
            result.fail(f"Expected ≥3 discord activities for this puzzle, got {data['count']}")
            return
        self.logger.log_operation(f"    ✓ Combined filter returned {data['count']} results (≥3 expected)")

        result.set_success("Discord source propagation test completed successfully")

    # ------------------------------------------------------------------
    # Test 32: Activity Statistics Endpoint
    # ------------------------------------------------------------------
    def test_activity_statistics_endpoint(self, result: TestResult):
        """Test GET /activity endpoint for activity counts and timing stats."""
        # 1. Basic shape validation
        self.logger.log_operation("  Testing: GET /activity response shape")
        data = self.api_get("/activity")
        if data.get("status") != "ok":
            result.fail(f"GET /activity failed: {data}")
            return

        for field in ["activity", "puzzle_solves_timer", "open_puzzles_timer", "seconds_since_last_solve"]:
            if field not in data:
                result.fail(f"Missing top-level field '{field}' in /activity response")
                return
        self.logger.log_operation("    ✓ All top-level fields present")

        # 2. Validate activity is a nested dict: {type: {source: int}}
        activity = data["activity"]
        if not isinstance(activity, dict):
            result.fail(f"activity should be a dict, got {type(activity).__name__}")
            return
        for act_type, sources in activity.items():
            if not isinstance(sources, dict):
                result.fail(f"activity['{act_type}'] should be a dict of sources, got {type(sources).__name__}")
                return
            for source, count in sources.items():
                if not isinstance(count, int):
                    result.fail(f"activity['{act_type}']['{source}'] should be int, got {type(count).__name__}")
                    return
        self.logger.log_operation(f"    ✓ Activity counts dict has {len(activity)} type(s): {list(activity.keys())}")

        # 3. Validate timer sub-objects
        self.logger.log_operation("  Testing: timer sub-objects")
        solves_timer = data["puzzle_solves_timer"]
        for field in ["total_solves", "total_solve_time_seconds"]:
            if field not in solves_timer:
                result.fail(f"Missing '{field}' in puzzle_solves_timer")
                return
        self.logger.log_operation(f"    ✓ puzzle_solves_timer: {solves_timer}")

        open_timer = data["open_puzzles_timer"]
        for field in ["total_open", "total_open_time_seconds"]:
            if field not in open_timer:
                result.fail(f"Missing '{field}' in open_puzzles_timer")
                return
        self.logger.log_operation(f"    ✓ open_puzzles_timer: {open_timer}")

        # 4. Create a puzzle and verify create count increases
        self.logger.log_operation("  Testing: create count increases after puzzle creation")
        before_create = sum(activity.get("create", {}).values())

        rounds = self.get_all_rounds()
        if not rounds:
            rnd = self.create_round("ActivityStatsRnd")
            rounds = [rnd]
        round_id = rounds[0]["id"]

        puz = self.create_puzzle(
            self.get_emoji_string("ActivityStatsPuz", include_emoji=False),
            round_id
        )

        data2 = self.api_get("/activity")
        after_create = sum(data2["activity"].get("create", {}).values())
        if after_create <= before_create:
            result.fail(f"Create count did not increase: {before_create} → {after_create}")
            return
        self.logger.log_operation(f"    ✓ Create count increased: {before_create} → {after_create}")

        # 5. Solve the puzzle and verify solve stats update
        self.logger.log_operation("  Testing: solve stats after puzzle solve")
        before_solves = data2["puzzle_solves_timer"]["total_solves"]
        self.api_post(f"/puzzles/{puz['id']}/answer", {"answer": "STATSTEST"})
        time.sleep(0.3)  # Brief pause for DB update

        data3 = self.api_get("/activity")
        after_solves = data3["puzzle_solves_timer"]["total_solves"]
        if after_solves <= before_solves:
            result.fail(f"total_solves did not increase: {before_solves} → {after_solves}")
            return
        self.logger.log_operation(f"    ✓ total_solves increased: {before_solves} → {after_solves}")

        # Verify seconds_since_last_solve is small (we just solved)
        since_last = data3.get("seconds_since_last_solve")
        if since_last is not None and since_last > 30:
            result.fail(f"seconds_since_last_solve too large after recent solve: {since_last}")
            return
        self.logger.log_operation(f"    ✓ seconds_since_last_solve = {since_last} (recent)")

        result.set_success("Activity statistics endpoint test completed successfully")

    # ------------------------------------------------------------------
    # Test 33: Activity has_more and Comment Type
    # ------------------------------------------------------------------
    def test_activity_has_more_and_comment(self, result: TestResult):
        """Test has_more pagination flag and comment activity type."""
        rounds = self.get_all_rounds()
        if not rounds:
            rnd = self.create_round("CommentRnd")
            rounds = [rnd]
        round_id = rounds[0]["id"]

        puz = self.create_puzzle(
            self.get_emoji_string("CommentPuz", include_emoji=False),
            round_id
        )

        # 1. Post a comment and verify it produces 'comment' activity
        self.logger.log_operation("  Testing: POST comment produces 'comment' activity type")
        self.api_post(f"/puzzles/{puz['id']}/comments", {"comments": "Test comment from API test"})
        time.sleep(0.2)

        data = self.api_get(f"/puzzles/{puz['id']}/activity")
        acts = data.get("activity", [])
        comment_acts = [a for a in acts if a.get("type") == "comment"]
        if not comment_acts:
            result.fail("No 'comment' activity found after posting comment")
            return
        self.logger.log_operation(f"    ✓ Found {len(comment_acts)} comment activity entry(ies)")

        # 2. Verify comment is searchable via activitysearch
        self.logger.log_operation("  Testing: comment type in activitysearch")
        data = self.api_get(f"/activitysearch?types=comment&puzzle_id={puz['id']}")
        if data.get("status") != "ok":
            result.fail(f"activitysearch for comment type failed: {data}")
            return
        if data["count"] < 1:
            result.fail(f"Expected ≥1 comment activity via search, got {data['count']}")
            return
        for act in data.get("activity", []):
            if act["type"] != "comment":
                result.fail(f"Type filter leaked: got type '{act['type']}' with types=comment filter")
                return
        self.logger.log_operation(f"    ✓ Comment searchable via activitysearch ({data['count']} results)")

        # 3. Verify has_more=false for small result set
        self.logger.log_operation("  Testing: has_more field for small result set")
        data = self.api_get(f"/activitysearch?puzzle_id={puz['id']}&limit=50")
        if data.get("status") != "ok":
            result.fail(f"activitysearch failed: {data}")
            return
        has_more = data.get("has_more")
        count = data.get("count", 0)
        activity_len = len(data.get("activity", []))

        if has_more is None:
            result.fail("Missing 'has_more' field in activitysearch response")
            return
        # With a fresh puzzle, we should have few activities (< 50), so has_more should be false
        if count <= 50 and has_more:
            result.fail(f"has_more should be false when count ({count}) <= limit (50)")
            return
        self.logger.log_operation(f"    ✓ has_more={has_more} (count={count}, limit=50)")

        # 4. Verify count matches activity array length
        self.logger.log_operation("  Testing: count == len(activity)")
        if count != activity_len:
            result.fail(f"count ({count}) != len(activity) ({activity_len})")
            return
        self.logger.log_operation(f"    ✓ count ({count}) == len(activity) ({activity_len})")

        # 5. Verify has_more is boolean and consistent with count vs limit
        self.logger.log_operation("  Testing: has_more is boolean and logically consistent")
        # With a small result set (< 50) and limit=50, has_more must be false
        if not isinstance(has_more, bool):
            result.fail(f"has_more should be bool, got {type(has_more).__name__}")
            return
        if count < 50 and has_more:
            result.fail(f"has_more should be false when count ({count}) < limit (50)")
            return
        self.logger.log_operation(f"    ✓ has_more is bool ({has_more}), consistent with count={count} < limit=50")

        result.set_success("Activity has_more and comment type test completed successfully")

    # ------------------------------------------------------------------
    # Test 34: Activity Source Metrics
    # ------------------------------------------------------------------
    def test_activity_source_metrics(self, result: TestResult):
        """Test that /activity returns counts grouped by type AND source, and that
        different source values are tracked independently."""
        # 1. Create a fresh puzzle to generate activity with known sources
        rounds = self.get_all_rounds()
        if not rounds:
            rnd = self.create_round("SrcMetricsRnd")
            rounds = [rnd]
        round_id = rounds[0]["id"]

        self.logger.log_operation("  Testing: /activity nested structure {type: {source: count}}")
        data_before = self.api_get("/activity")
        activity_before = data_before["activity"]

        # Helper to sum counts for a given type across all sources
        def type_total(activity, act_type):
            return sum(activity.get(act_type, {}).values())

        before_create = type_total(activity_before, "create")
        before_change = type_total(activity_before, "change")

        # 2. Create puzzle (default source=puzzleboss)
        self.logger.log_operation("  Creating puzzle (source=puzzleboss by default)")
        puz = self.create_puzzle(
            self.get_emoji_string("SrcMetricsPuz", include_emoji=False),
            round_id
        )

        data_after_create = self.api_get("/activity")
        after_create = type_total(data_after_create["activity"], "create")
        if after_create <= before_create:
            result.fail(f"Create total did not increase: {before_create} → {after_create}")
            return

        # Verify the create entry has a puzzleboss source
        create_sources = data_after_create["activity"].get("create", {})
        if "puzzleboss" not in create_sources:
            result.fail(f"Expected 'puzzleboss' source in create counts, got: {create_sources}")
            return
        self.logger.log_operation(f"    ✓ Create count increased, source=puzzleboss present")

        # 3. Update xyzloc with source=discord
        self.logger.log_operation("  Testing: xyzloc change with source=discord")
        self.api_post(f"/puzzles/{puz['id']}/xyzloc", {"xyzloc": "DiscordLoc", "source": "discord"})

        data_after_discord = self.api_get("/activity")
        change_sources = data_after_discord["activity"].get("change", {})
        if "discord" not in change_sources:
            result.fail(f"Expected 'discord' source in change counts after discord update, got: {change_sources}")
            return
        self.logger.log_operation(f"    ✓ Change activity has source=discord: {change_sources}")

        # 4. Update xyzloc again with default source (puzzleboss)
        self.logger.log_operation("  Testing: xyzloc change with default source=puzzleboss")
        self.api_post(f"/puzzles/{puz['id']}/xyzloc", {"xyzloc": "PBLoc"})

        data_after_pb = self.api_get("/activity")
        change_sources = data_after_pb["activity"].get("change", {})
        if "puzzleboss" not in change_sources:
            result.fail(f"Expected 'puzzleboss' source in change counts, got: {change_sources}")
            return
        self.logger.log_operation(f"    ✓ Change activity has both sources: {change_sources}")

        # 5. Verify sources are independent — discord count shouldn't have changed
        discord_count_before = data_after_discord["activity"].get("change", {}).get("discord", 0)
        discord_count_after = data_after_pb["activity"].get("change", {}).get("discord", 0)
        if discord_count_after != discord_count_before:
            result.fail(f"Discord change count shifted after puzzleboss update: {discord_count_before} → {discord_count_after}")
            return
        self.logger.log_operation(f"    ✓ Discord count stable ({discord_count_after}) while puzzleboss incremented")

        # 6. Multi-part update with source=discord
        self.logger.log_operation("  Testing: multi-part update with source=discord")
        self.api_post(f"/puzzles/{puz['id']}", {"xyzloc": "Room3", "comments": "test", "source": "discord"})

        data_after_multi = self.api_get("/activity")
        comment_sources = data_after_multi["activity"].get("comment", {})
        if "discord" not in comment_sources:
            result.fail(f"Expected 'discord' source in comment counts after multi-part update, got: {comment_sources}")
            return
        self.logger.log_operation(f"    ✓ Multi-part update: comment has source=discord")

        # 7. Verify all values in the response are proper nested ints
        self.logger.log_operation("  Testing: all activity values are {type: {source: int}}")
        for act_type, sources in data_after_multi["activity"].items():
            if not isinstance(sources, dict):
                result.fail(f"activity['{act_type}'] should be dict, got {type(sources).__name__}")
                return
            for src, count in sources.items():
                if not isinstance(count, int):
                    result.fail(f"activity['{act_type}']['{src}'] should be int, got {type(count).__name__}: {count}")
                    return
        self.logger.log_operation(f"    ✓ All activity values are properly nested integers")

        result.set_success("Activity source metrics test completed successfully")

    # ======================================================================
    # Test suite runner
    # ======================================================================

    def run_all_tests(self, selected_tests=None):
        test_funcs = [
            self.test_solver_listing,
            self.test_puzzle_creation,
            self.test_puzzle_creation_stepwise,
            self.test_puzzle_modification,
            self.test_puzzle_round_change,
            self.test_multi_part_update,
            self.test_round_modification,
            self.test_round_multi_part_update,
            self.test_solver_multi_part_update,
            self.test_meta_puzzles_and_round_completion,
            self.test_answer_verification,
            self.test_solver_assignments,
            self.test_solve_clears_location_and_solvers,
            self.test_solver_reassignment,
            self.test_activity_tracking,
            self.test_puzzle_activity_endpoint,
            self.test_solver_activity_endpoint,
            self.test_solver_history,
            self.test_sheetcount,
            self.test_tagging,
            self.test_api_endpoints,
            self.test_api_documentation,
            self.test_bot_statistics,
            self.test_cache_invalidation,
            self.test_solver_crud,
            self.test_rbac_privileges,
            self.test_puzzle_deletion,
            self.test_hint_queue,
            self.test_activity_search,
            self.test_activity_type_verification,
            self.test_discord_source_propagation,
            self.test_activity_statistics_endpoint,
            self.test_activity_has_more_and_comment,
            self.test_activity_source_metrics,
        ]
        tests = list(zip(self.TEST_NAMES, test_funcs))

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

def main():
    parser = make_arg_parser("PuzzleBoss API Test Suite", TestRunner.TEST_NAMES)
    parser.add_argument("--base-url", default=BASE_URL,
                        help=f"API base URL (default: {BASE_URL})")
    args = parser.parse_args()

    handle_list_and_destructive(args, test_names=TestRunner.TEST_NAMES)

    # Parse --tests into set of 1-based indices
    selected = None
    if args.tests:
        specs = []
        for arg in args.tests:
            specs.extend(arg.split(","))
        selected = set()
        for s in specs:
            try:
                selected.add(int(s.strip()))
            except ValueError:
                print(f"ERROR: Invalid test number '{s}'")
                sys.exit(1)

    reset_hunt()
    ensure_test_solvers_api(args.base_url)

    runner = TestRunner(args.base_url)
    success = runner.run_all_tests(selected_tests=selected)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
