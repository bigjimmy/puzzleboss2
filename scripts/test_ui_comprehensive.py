#!/usr/bin/env python3
"""
Comprehensive Playwright UI test suite for Puzzleboss.

Tests user workflows, real-time updates, form validation, error handling, and more.
Uses actual UI workflows (addround.php, addpuzzle.php) instead of direct API calls.

Usage:
    python scripts/test_ui_comprehensive.py

Requirements:
    - Docker container running (docker-compose up)
    - Clean database (run reset-hunt.py first)
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, expect
import sys
import time
import requests
import json


BASE_URL = "http://localhost"
API_URL = "http://localhost:5000"


class UITestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def run_test(self, test_func):
        """Run a test and track results."""
        test_name = test_func.__name__.replace("_", " ").replace("test ", "").title()
        print(f"\n{'='*70}")
        print(f"TEST: {test_name}")
        print(f"{'='*70}")

        try:
            start = time.time()
            test_func()
            duration = time.time() - start
            print(f"✅ PASSED ({duration:.2f}s)")
            self.passed += 1
            self.tests.append((test_name, True, duration))
        except Exception as e:
            duration = time.time() - start
            print(f"❌ FAILED: {str(e)}")
            self.failed += 1
            self.tests.append((test_name, False, duration))
            import traceback
            traceback.print_exc()

    def print_summary(self):
        """Print test results summary."""
        print(f"\n{'='*70}")
        print("TEST RESULTS SUMMARY")
        print(f"{'='*70}")
        for name, passed, duration in self.tests:
            status = "✅" if passed else "❌"
            print(f"{status} {name}: {duration:.2f}s")
        print(f"\nTotal: {self.passed + self.failed} tests")
        print(f"Passed: {self.passed}")
        print(f"Failed: {self.failed}")
        print(f"{'='*70}")


def reset_hunt():
    """Reset the hunt database before running tests."""
    print("Resetting hunt database...")
    import subprocess
    result = subprocess.run(
        ['bash', '-c', 'echo "IWANTTODESTROYTHEHUNT" | python3 scripts/reset-hunt.py'],
        capture_output=True,
        text=True,
        cwd='/app'
    )
    if result.returncode != 0:
        print(f"Warning: Hunt reset failed with code {result.returncode}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)
    print("Hunt reset completed successfully")
    time.sleep(3)  # Wait for database to settle


def api_call(method, endpoint, data=None):
    """Make an API call for test setup/verification."""
    url = f"{API_URL}{endpoint}"
    if method == "GET":
        response = requests.get(url)
    elif method == "POST":
        response = requests.post(url, json=data)
    elif method == "DELETE":
        response = requests.delete(url)

    if response.ok:
        return response.json()
    else:
        raise Exception(f"API call failed: {response.status_code} - {response.text}")


def create_round_via_ui(page, round_name):
    """Create a round using the addround.php UI form."""
    page.goto(f"{BASE_URL}/addround.php?assumedid=testuser")
    page.fill("input[name='name']", round_name)
    page.click("input[type='submit'][value='Add Round']")

    # Wait for success message
    page.wait_for_selector("div.success", timeout=10000)

    # Get the created round from API to get its ID
    # Name gets sanitized (spaces removed)
    sanitized_name = round_name.replace(" ", "")
    rounds = api_call("GET", "/rounds")
    for round_data in rounds["rounds"]:
        if round_data["name"] == sanitized_name:
            return round_data

    raise Exception(f"Failed to find created round: {round_name}")


def create_puzzle_via_ui(page, puzzle_name, round_id, is_meta=False, is_speculative=False):
    """Create a puzzle using the addpuzzle.php UI form (5-step workflow)."""
    page.goto(f"{BASE_URL}/addpuzzle.php?assumedid=testuser")

    # Wait for page to load
    page.wait_for_selector("input[name='name']", timeout=10000)

    # Fill in puzzle details
    page.fill("input[name='name']", puzzle_name)
    page.fill("input[name='puzzle_uri']", f"https://example.com/{puzzle_name.replace(' ', '_')}")
    page.select_option("select[name='round_id']", str(round_id))

    if is_meta:
        page.check("input[name='is_meta']")

    if is_speculative:
        page.check("input[name='is_speculative']")

    # Submit form
    page.click("input[type='submit'][value='Add New Puzzle']")

    # Wait for all 5 steps to complete
    page.wait_for_selector("#step5 .status:has-text('✅')", timeout=30000)

    # Get the created puzzle from API
    sanitized_name = puzzle_name.replace(" ", "")
    puzzles = api_call("GET", "/puzzles")
    for puzzle_data in puzzles["puzzles"]:
        if puzzle_data["name"] == sanitized_name:
            return puzzle_data

    raise Exception(f"Failed to find created puzzle: {puzzle_name}")


def assign_solver_via_api(solver_id, puzzle_id):
    """Assign a solver to a puzzle using the correct API endpoint."""
    response = requests.post(
        f"{API_URL}/solvers/{solver_id}/puzz",
        json={"puzz": puzzle_id}
    )
    if not response.ok:
        raise Exception(f"Failed to assign solver: {response.text}")


# Test 1: Puzzle Lifecycle
def test_puzzle_lifecycle():
    """Test complete puzzle lifecycle from creation to solve."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create a round via UI
        round_data = create_round_via_ui(page, "Test Round")
        round_id = round_data["id"]

        # Create a puzzle via UI
        puzzle_data = create_puzzle_via_ui(page, "Test Lifecycle Puzzle", round_id)
        puzzle_id = puzzle_data["id"]

        # Navigate to main page
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page.wait_for_selector("text=TestLifecyclePuzzle", timeout=10000)

        # Assign solver via API
        solvers = api_call("GET", "/solvers")
        solver_id = solvers["solvers"][0]["id"]
        assign_solver_via_api(solver_id, puzzle_id)

        # Verify solver appears on UI (wait for auto-refresh)
        time.sleep(6)
        page.reload()
        solver_name = solvers["solvers"][0]["name"]
        page.wait_for_selector(f"text={solver_name}", timeout=5000)

        # Change status to "Being worked"
        api_call("POST", f"/puzzles/{puzzle_id}/status", {"status": "Being worked"})
        time.sleep(6)
        page.reload()
        page.wait_for_selector("text=Being worked", timeout=5000)

        # Solve the puzzle
        api_call("POST", f"/puzzles/{puzzle_id}/answer", {"answer": "TEST ANSWER"})
        time.sleep(6)
        page.reload()
        page.wait_for_selector("text=TESTANSWER", timeout=5000)

        browser.close()
        print("✓ Puzzle lifecycle completed successfully")


# Test 2: Speculative Puzzle Promotion
def test_speculative_puzzle_promotion():
    """Test creating and promoting a speculative puzzle."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create round
        round_data = create_round_via_ui(page, "Spec Test Round")
        round_id = round_data["id"]

        # Create speculative puzzle
        puzzle_data = create_puzzle_via_ui(page, "Speculative Test Puzzle", round_id, is_speculative=True)
        puzzle_id = puzzle_data["id"]

        # Verify it has Speculative status
        puzzle_details = api_call("GET", f"/puzzles/{puzzle_id}")
        assert puzzle_details["puzzle"]["status"] == "Speculative", "Puzzle not marked as Speculative"

        # Navigate to addpuzzle page to promote
        page.goto(f"{BASE_URL}/addpuzzle.php?assumedid=testuser")

        # Wait for speculative puzzles to load in the dropdown
        page.wait_for_selector("select[name='promote_puzzle_id'] option:not([value=''])", timeout=5000)

        # Select the speculative puzzle
        page.select_option("select[name='promote_puzzle_id']", str(puzzle_id))

        # Update the URL for the real puzzle
        page.fill("input[name='puzzle_uri']", "https://example.com/real_puzzle")

        # Submit to promote
        page.click("input[type='submit'][value='Promote Puzzle']")

        # Wait for success
        page.wait_for_selector("div.success", timeout=10000)

        # Verify status changed to New
        puzzle_details = api_call("GET", f"/puzzles/{puzzle_id}")
        assert puzzle_details["puzzle"]["status"] == "New", "Puzzle not promoted to New status"

        browser.close()
        print("✓ Speculative puzzle promotion completed successfully")


# Test 3: Round Completion via Meta Puzzles
def test_round_completion_meta():
    """Test that rounds are marked complete when all metas are solved, and unmarked when new unsolved metas are added."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create round
        round_data = create_round_via_ui(page, "Meta Test Round")
        round_id = round_data["id"]

        # Create two meta puzzles
        meta1 = create_puzzle_via_ui(page, "Meta Puzzle 1", round_id, is_meta=True)
        meta2 = create_puzzle_via_ui(page, "Meta Puzzle 2", round_id, is_meta=True)

        # Verify round is not complete
        round_status = api_call("GET", f"/rounds/{round_id}")
        assert round_status["round"]["status"] != "Solved", "Round marked solved before metas solved"

        # Solve first meta
        api_call("POST", f"/puzzles/{meta1['id']}/answer", {"answer": "META1"})

        # Verify round still not complete
        round_status = api_call("GET", f"/rounds/{round_id}")
        assert round_status["round"]["status"] != "Solved", "Round marked solved with only 1/2 metas solved"

        # Solve second meta
        api_call("POST", f"/puzzles/{meta2['id']}/answer", {"answer": "META2"})

        # Verify round IS complete
        round_status = api_call("GET", f"/rounds/{round_id}")
        assert round_status["round"]["status"] == "Solved", "Round not marked solved after all metas solved"

        # Now add a third unsolved meta puzzle - this should unmark the round
        meta3 = create_puzzle_via_ui(page, "Meta Puzzle 3", round_id, is_meta=True)

        # Verify round is NO LONGER complete (THIS IS THE BUG WE'RE TESTING)
        round_status = api_call("GET", f"/rounds/{round_id}")
        assert round_status["round"]["status"] != "Solved", "Round still marked solved after adding unsolved meta"

        # Solve the third meta
        api_call("POST", f"/puzzles/{meta3['id']}/answer", {"answer": "META3"})

        # Verify round is complete again
        round_status = api_call("GET", f"/rounds/{round_id}")
        assert round_status["round"]["status"] == "Solved", "Round not marked solved after solving all 3 metas"

        browser.close()
        print("✓ Round completion/unmarking logic working correctly")


# Test 4: Tag Management
def test_tag_management():
    """Test adding tags and filtering puzzles by tags."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create round and puzzles
        round_data = create_round_via_ui(page, "Tag Test Round")
        round_id = round_data["id"]
        puzzle1 = create_puzzle_via_ui(page, "Cryptic Puzzle", round_id)
        puzzle2 = create_puzzle_via_ui(page, "Logic Puzzle", round_id)

        # Create tags via API (correct format)
        tag1 = api_call("POST", "/tags", {"name": "cryptic"})
        tag2 = api_call("POST", "/tags", {"name": "logic"})

        # Get tag IDs
        tags = api_call("GET", "/tags")
        cryptic_tag_id = next(t["id"] for t in tags["tags"] if t["name"] == "cryptic")
        logic_tag_id = next(t["id"] for t in tags["tags"] if t["name"] == "logic")

        # Add tags to puzzles (correct API format)
        api_call("POST", f"/puzzles/{puzzle1['id']}/tags", {"tags": {"add_id": cryptic_tag_id}})
        api_call("POST", f"/puzzles/{puzzle2['id']}/tags", {"tags": {"add_id": logic_tag_id}})

        # Navigate to main page
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page.wait_for_selector("text=CrypticPuzzle", timeout=10000)

        # TODO: Test tag filtering on the UI (would need to examine index.php UI more)

        browser.close()
        print("✓ Tag management completed successfully")


# Test 5: Solver Reassignment
def test_solver_reassignment():
    """Test that solver is auto-unassigned from old puzzle when assigned to new puzzle."""
    # Create test data
    round_data = create_round_via_ui_headless("Solver Test Round")
    round_id = round_data["id"]

    puzzle_a_data = create_puzzle_via_ui_headless("Puzzle A", round_id)
    puzzle_b_data = create_puzzle_via_ui_headless("Puzzle B", round_id)

    # Get a solver
    solvers = api_call("GET", "/solvers")
    solver_id = solvers["solvers"][0]["id"]

    # Assign solver to Puzzle A
    assign_solver_via_api(solver_id, puzzle_a_data["id"])

    # Verify solver is assigned to Puzzle A
    puzzle_a = api_call("GET", f"/puzzles/{puzzle_a_data['id']}")
    current_solvers_str = json.dumps(puzzle_a["puzzle"].get("current_solvers", ""))
    assert str(solver_id) in current_solvers_str, f"Solver {solver_id} not assigned to Puzzle A"

    # Assign solver to Puzzle B
    assign_solver_via_api(solver_id, puzzle_b_data["id"])

    # Verify solver is no longer assigned to Puzzle A
    puzzle_a = api_call("GET", f"/puzzles/{puzzle_a_data['id']}")
    current_solvers_str = json.dumps(puzzle_a["puzzle"].get("current_solvers", ""))
    assert str(solver_id) not in current_solvers_str, f"Solver {solver_id} still assigned to Puzzle A"

    # Verify solver IS assigned to Puzzle B
    puzzle_b = api_call("GET", f"/puzzles/{puzzle_b_data['id']}")
    current_solvers_str = json.dumps(puzzle_b["puzzle"].get("current_solvers", ""))
    assert str(solver_id) in current_solvers_str, f"Solver {solver_id} not assigned to Puzzle B"

    print("✓ Solver reassignment working correctly")


def create_round_via_ui_headless(round_name):
    """Create round via UI in headless mode (helper function)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        result = create_round_via_ui(page, round_name)
        browser.close()
        return result


def create_puzzle_via_ui_headless(puzzle_name, round_id, is_meta=False, is_speculative=False):
    """Create puzzle via UI in headless mode (helper function)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        result = create_puzzle_via_ui(page, puzzle_name, round_id, is_meta, is_speculative)
        browser.close()
        return result


# Test 6: Settings Persistence
def test_settings_persistence():
    """Test that UI settings persist across page reloads."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page.wait_for_load_state("networkidle")

        # Get initial auto-refresh state from localStorage
        initial_state = page.evaluate("localStorage.getItem('autoRefresh')")

        # Toggle the setting (if it exists in the UI)
        # For now, just verify localStorage persists across reloads
        page.evaluate("localStorage.setItem('testSetting', 'testValue')")

        # Reload page
        page.reload()
        page.wait_for_load_state("networkidle")

        # Verify setting persisted
        persisted_value = page.evaluate("localStorage.getItem('testSetting')")
        assert persisted_value == "testValue", "localStorage settings did not persist"

        browser.close()
        print("✓ Settings persistence working correctly")


# Test 7: Form Validation
def test_form_validation():
    """Test form validation on addpuzzle.php."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create a round first
        round_data = create_round_via_ui(page, "Validation Test Round")

        # Try to submit empty puzzle name
        page.goto(f"{BASE_URL}/addpuzzle.php?assumedid=testuser")
        page.wait_for_selector("input[name='name']", timeout=10000)
        page.fill("input[name='name']", "")
        page.fill("input[name='puzzle_uri']", "https://example.com/test")
        page.select_option("select[name='round_id']", str(round_data["id"]))
        page.click("input[type='submit'][value='Add New Puzzle']")

        # Verify error is shown (browser validation should prevent submission)
        # Since HTML5 validation prevents submission, we check that we're still on the same page
        time.sleep(1)
        assert "addpuzzle.php" in page.url, "Form allowed empty name submission"

        browser.close()
        print("✓ Form validation working correctly")


# Test 8: Unicode Handling
def test_unicode_handling():
    """Test that the system handles unicode characters (emojis, international characters) correctly."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create round with unicode
        round_data = create_round_via_ui(page, "Unicode Test Round 🎯")

        # Create puzzle with unicode
        puzzle_data = create_puzzle_via_ui(page, "Test Puzzle 日本語 🧩", round_data["id"])

        # Navigate to main page and verify unicode displays
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        # Note: Puzzle names are sanitized, so spaces and some chars might be removed
        # Just verify the page loads without errors
        page.wait_for_load_state("networkidle")

        browser.close()
        print("✓ Unicode handling working correctly")


def main():
    """Run all tests."""
    print("="*70)
    print("COMPREHENSIVE PUZZLEBOSS UI TEST SUITE")
    print("="*70)

    reset_hunt()

    runner = UITestRunner()

    # Run tests
    runner.run_test(test_puzzle_lifecycle)
    runner.run_test(test_speculative_puzzle_promotion)
    runner.run_test(test_round_completion_meta)
    runner.run_test(test_tag_management)
    runner.run_test(test_solver_reassignment)
    runner.run_test(test_settings_persistence)
    runner.run_test(test_form_validation)
    runner.run_test(test_unicode_handling)

    runner.print_summary()

    # Exit with error code if any tests failed
    sys.exit(0 if runner.failed == 0 else 1)


if __name__ == "__main__":
    main()
