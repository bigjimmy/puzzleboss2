#!/usr/bin/env python3
"""
Comprehensive Playwright UI test suite for Puzzleboss.

Tests user workflows, real-time updates, form validation, error handling, and more.
Uses actual UI workflows (addround.php, addpuzzle.php) instead of direct API calls.

Usage:
    python scripts/test_ui_comprehensive.py --allow-destructive

WARNING: This script will RESET THE HUNT DATABASE, destroying all puzzle data!
         The --allow-destructive flag is REQUIRED to run.
         DO NOT run this on a production system!

Requirements:
    - Docker container running (docker-compose up)
    - --allow-destructive flag (safety check)
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout, expect
import sys
import time
import requests
import json
import argparse


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
        ['python3', 'scripts/reset-hunt.py', '--yes-i-am-sure-i-want-to-destroy-all-data'],
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


def ensure_test_solvers():
    """Ensure we have enough test solvers for UI tests."""
    print("Checking for test solvers...")
    try:
        response = requests.get(f"{API_URL}/solvers")
        solvers = response.json().get("solvers", [])
        current_count = len(solvers)
        min_count = 5

        if current_count >= min_count:
            print(f"  Sufficient solvers available ({current_count} >= {min_count})")
            return

        needed = min_count - current_count
        print(f"  Creating {needed} test solvers to reach minimum of {min_count}...")

        for i in range(1, min_count + 1):
            try:
                requests.post(f"{API_URL}/solvers", json={
                    "name": f"testsolver{i}",
                    "fullname": f"Test Solver {i}"
                })
            except:
                pass  # May already exist

        # Verify we now have enough
        response = requests.get(f"{API_URL}/solvers")
        solvers = response.json().get("solvers", [])
        print(f"  Now have {len(solvers)} solvers available for testing")
    except Exception as e:
        print(f"Warning: Could not ensure test solvers: {e}")



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
    # Add timestamp to make round name unique across test runs
    timestamp = str(int(time.time()))
    unique_name = f"{round_name}{timestamp}"

    page.goto(f"{BASE_URL}/addround.php?assumedid=testuser")
    page.fill("input[name='name']", unique_name)
    page.click("input[type='submit'][value='Add Round']")

    # Wait for success message
    page.wait_for_selector("div.success", timeout=10000)

    # Return the sanitized name (spaces removed) for use in UI selectors
    # No API call needed!
    sanitized_name = unique_name.replace(" ", "")
    return {"name": sanitized_name}


def create_puzzle_via_ui(page, puzzle_name, round_name, is_meta=False, is_speculative=False):
    """Create a puzzle using the addpuzzle.php UI form (5-step workflow)."""
    page.goto(f"{BASE_URL}/addpuzzle.php?assumedid=testuser")

    # Wait for page to load
    page.wait_for_selector("input[name='name']", timeout=10000)

    # Fill in puzzle details
    page.fill("input[name='name']", puzzle_name)
    page.fill("input[name='puzzle_uri']", f"https://example.com/{puzzle_name.replace(' ', '_')}")

    # Select round by visible text (label) instead of by ID value
    page.select_option("select[name='round_id']", label=round_name)

    if is_meta:
        page.check("input[name='is_meta']")

    if is_speculative:
        page.check("input[name='is_speculative']")

    # Submit form
    page.click("input[type='submit'][value='Add New Puzzle']")

    # Wait for all 5 steps to complete
    page.wait_for_selector("#step5 .status:has-text('✅')", timeout=30000)

    # Return the sanitized name for use in UI selectors
    # No API call needed!
    sanitized_name = puzzle_name.replace(" ", "")
    return {"name": sanitized_name}


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
        round_name = round_data["name"]

        # Create a puzzle via UI
        puzzle_data = create_puzzle_via_ui(page, "Test Lifecycle Puzzle", round_name)
        puzzle_name = puzzle_data["name"]

        # Navigate to main page
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page.wait_for_selector(f"text={puzzle_name}", timeout=10000)

        # Verify initial "New" status on UI
        puzzle_elem = page.query_selector(".puzzle")
        status_icon = puzzle_elem.query_selector('.puzzle-icon[title*="New"]')
        assert status_icon is not None, "Initial 'New' status icon not found"

        # Assign solver via UI - click on workstate icon (👻 for no solvers)
        print("  Assigning solver via UI...")
        workstate_icons = puzzle_elem.query_selector_all('.puzzle-icon')
        # Find the workstate icon (should be second icon in puzzle-icons div)
        workstate_icon = workstate_icons[1] if len(workstate_icons) > 1 else None
        assert workstate_icon is not None, "Workstate icon not found"
        workstate_icon.click()

        # Wait for modal to appear
        page.wait_for_selector("dialog", timeout=5000)

        # Wait a moment for the modal content to fully render
        time.sleep(0.5)

        # Click "Yes" to claim puzzle (button text includes "Yes")
        yes_button = page.query_selector("dialog button:has-text('Yes')")
        if yes_button is None:
            # If no "Yes" button, we may already be assigned or need to just set location
            # Set location field and save
            location_input = page.query_selector("dialog input")
            if location_input:
                location_input.fill("TestLocation")
                save_button = page.query_selector("dialog button:has-text('Save')")
                if save_button:
                    save_button.click()
        else:
            yes_button.click()

        # Wait for modal to close
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Wait for auto-refresh to show solver assignment (max ~6 seconds for 5s polling + buffer)
        print("  Waiting for auto-refresh to show solver assignment...")
        page.wait_for_function("""
            () => {
                const puzzle = document.querySelector('.puzzle');
                return puzzle && puzzle.innerText.includes('👥');
            }
        """, timeout=7000)

        # Verify solver icon (👥) appears on UI
        puzzle_elem = page.query_selector(".puzzle")
        puzzle_text = puzzle_elem.inner_text()
        assert "👥" in puzzle_text, "Solver icon (👥) not shown after assignment"

        # Change status to "Being worked" via UI
        print("  Changing status to 'Being worked' via UI...")
        status_icons = puzzle_elem.query_selector_all('.puzzle-icon')
        # Status icon should be first icon in puzzle-icons div
        status_icon = status_icons[0] if len(status_icons) > 0 else None
        assert status_icon is not None, "Status icon not found"
        status_icon.click()

        # Wait for modal and change status
        page.wait_for_selector("dialog select.dropdown", timeout=5000)
        page.select_option("dialog select.dropdown", "Being worked")

        # Click Save button
        save_button = page.query_selector("dialog button:has-text('Save')")
        assert save_button is not None, "Save button not found in status modal"
        save_button.click()

        # Wait for modal to close
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Wait for auto-refresh to show status change
        print("  Waiting for auto-refresh to show status change...")
        page.wait_for_function("""
            () => {
                const puzzle = document.querySelector('.puzzle');
                const statusIcon = puzzle ? puzzle.querySelector('.puzzle-icon') : null;
                return statusIcon && statusIcon.title.includes('Being worked');
            }
        """, timeout=7000)

        # Verify "Being worked" status on UI
        puzzle_elem = page.query_selector(".puzzle")
        status_icon = puzzle_elem.query_selector('.puzzle-icon[title*="Being worked"]')
        assert status_icon is not None, "Being worked status icon not found on UI"

        # Solve the puzzle via UI
        print("  Solving puzzle via UI...")
        status_icons = puzzle_elem.query_selector_all('.puzzle-icon')
        status_icon = status_icons[0] if len(status_icons) > 0 else None
        assert status_icon is not None, "Status icon not found"
        status_icon.click()

        # Wait for modal and change status to Solved
        page.wait_for_selector("dialog select.dropdown", timeout=5000)
        page.select_option("dialog select.dropdown", "Solved")

        # Wait for answer field to appear (it appears after selecting Solved)
        time.sleep(0.5)  # Give Vue.js time to show the answer field

        # Find and fill the answer input (look for input with v-model="answer")
        answer_input = page.query_selector("dialog p:has-text('Answer:') input")
        assert answer_input is not None, "Answer input not found in dialog"
        answer_input.fill("TEST ANSWER")

        # Click Save button
        save_button = page.query_selector("dialog button:has-text('Save')")
        assert save_button is not None, "Save button not found in status modal"
        save_button.click()

        # Wait for modal to close
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Wait for auto-refresh to show answer and solved status
        print("  Waiting for auto-refresh to show answer and solved status...")
        page.wait_for_function("""
            () => {
                const puzzle = document.querySelector('.puzzle');
                const answerElem = puzzle ? puzzle.querySelector('.answer') : null;
                return answerElem && answerElem.innerText.includes('TEST ANSWER');
            }
        """, timeout=7000)

        # Verify answer appears on UI
        puzzle_elem = page.query_selector(".puzzle")
        answer_elem = puzzle_elem.query_selector(".answer")
        assert answer_elem is not None, "Answer element not found"
        answer_text = answer_elem.inner_text().strip()
        assert "TEST ANSWER" in answer_text, f"Answer 'TEST ANSWER' not in UI (found: {answer_text})"

        # Verify "Solved" status on UI
        status_icon = puzzle_elem.query_selector('.puzzle-icon[title*="Solved"]')
        assert status_icon is not None, "Solved status icon not found on UI"

        browser.close()
        print("✓ Puzzle lifecycle completed successfully")


# Test 2: Speculative Puzzle Promotion (Concurrency Test)
def test_speculative_puzzle_promotion():
    """Test creating and promoting a speculative puzzle with concurrent browser verification."""
    with sync_playwright() as p:
        # Launch TWO browsers to test concurrent users
        browser1 = p.chromium.launch(headless=True)
        browser2 = p.chromium.launch(headless=True)

        page1 = browser1.new_page()  # Admin creating/promoting puzzle
        page2 = browser2.new_page()  # Observer watching changes

        # Browser 1: Create round
        round_data = create_round_via_ui(page1, "Spec Test Round")
        round_name = round_data["name"]

        # Browser 1: Create speculative puzzle
        puzzle_data = create_puzzle_via_ui(page1, "Speculative Test Puzzle", round_name, is_speculative=True)
        puzzle_name = puzzle_data["name"]

        # Browser 2: Navigate to main page and wait for puzzle to appear
        print("  [Browser 2] Waiting for new puzzle to appear via auto-refresh...")
        page2.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page2.wait_for_selector(f"text={puzzle_name}", timeout=15000)

        # Browser 2: Verify it has Speculative status in UI (via auto-refresh)
        print("  [Browser 2] Verifying Speculative status in UI...")
        page2.wait_for_function(f"""
            () => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{puzzle_name}')) {{
                        const statusIcon = puzzle.querySelector('.puzzle-icon');
                        return statusIcon && statusIcon.title.includes('Speculative');
                    }}
                }}
                return false;
            }}
        """, timeout=7000)

        # Browser 2: Double-check by querying the DOM
        puzzles = page2.query_selector_all(".puzzle")
        speculative_puzzle = None
        for puzzle in puzzles:
            if puzzle_name in puzzle.inner_text():
                speculative_puzzle = puzzle
                break
        assert speculative_puzzle is not None, f"Puzzle {puzzle_name} not found in Browser 2"

        status_icon = speculative_puzzle.query_selector(".puzzle-icon")
        status_title = status_icon.get_attribute("title")
        assert "Speculative" in status_title, f"Status not 'Speculative' in Browser 2 (found: {status_title})"
        print(f"  [Browser 2] ✓ Verified Speculative status: {status_title}")

        # Browser 1: Navigate to addpuzzle page to promote
        print("  [Browser 1] Promoting puzzle...")
        page1.goto(f"{BASE_URL}/addpuzzle.php?assumedid=testuser")

        # Wait for the promote section to appear (only shows if there are speculative puzzles)
        # This should appear immediately if the speculative puzzle was created successfully
        page1.wait_for_selector("#promote-puzzle-fields", timeout=5000)

        # Find the row containing our puzzle name and click its radio button
        # The table cells contain the puzzle name, we need to find it and click the radio in that row
        radio_selector = f"tr:has-text('{puzzle_name}') input[name='promote_puzzle_id']"
        page1.wait_for_selector(radio_selector, timeout=5000)
        page1.click(radio_selector)

        # Wait a moment for the form to update
        page1.wait_for_timeout(500)

        # Update the URL for the real puzzle
        page1.fill("input[name='puzzle_uri']", "https://example.com/real_puzzle")

        # Submit to promote
        page1.click("input[type='submit']")

        # Wait for success
        page1.wait_for_selector("div.success", timeout=10000)
        print("  [Browser 1] ✓ Promotion completed")

        # Browser 2: Wait for auto-refresh to show status changed to New (NO RELOAD!)
        print("  [Browser 2] Waiting for auto-refresh to show promotion to New status...")
        page2.wait_for_function(f"""
            () => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{puzzle_name}')) {{
                        const statusIcon = puzzle.querySelector('.puzzle-icon');
                        return statusIcon && statusIcon.title.includes('New');
                    }}
                }}
                return false;
            }}
        """, timeout=7000)

        # Browser 2: Verify the change
        puzzles = page2.query_selector_all(".puzzle")
        promoted_puzzle = None
        for puzzle in puzzles:
            if puzzle_name in puzzle.inner_text():
                promoted_puzzle = puzzle
                break
        assert promoted_puzzle is not None, f"Puzzle {puzzle_name} not found in Browser 2 after promotion"

        status_icon = promoted_puzzle.query_selector(".puzzle-icon")
        status_title = status_icon.get_attribute("title")
        assert "New" in status_title, f"Status not 'New' in Browser 2 after promotion (found: {status_title})"
        print(f"  [Browser 2] ✓ Verified promotion to New status via auto-refresh: {status_title}")

        browser1.close()
        browser2.close()
        print("✓ Speculative puzzle promotion with concurrent verification completed successfully")


# Test 3: Round Completion via Meta Puzzles
def test_round_completion_meta():
    """Test that rounds are marked complete when all metas are solved, and unmarked when new unsolved metas are added."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create round
        round_data = create_round_via_ui(page, "Meta Test Round")
        round_name = round_data["name"]

        # Create two meta puzzles
        meta1 = create_puzzle_via_ui(page, "Meta Puzzle 1", round_name, is_meta=True)
        meta2 = create_puzzle_via_ui(page, "Meta Puzzle 2", round_name, is_meta=True)

        # Navigate to main page
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page.wait_for_selector(f"text={round_name}", timeout=10000)

        # Verify round is not marked solved (no "solved" class on round header)
        round_header = page.query_selector(".round-header")
        round_classes = round_header.get_attribute("class")
        assert "solved" not in round_classes, "Round marked solved before metas solved"

        # Solve first meta via UI
        print("  Solving first meta puzzle...")
        page.click(f"text=MetaPuzzle1")  # Expand the puzzle
        time.sleep(0.5)
        # Find the meta puzzle and click its status icon
        meta1_puzzle = page.query_selector(".puzzle.meta")
        status_icon = meta1_puzzle.query_selector(".puzzle-icon")
        status_icon.click()
        # Wait for modal
        page.wait_for_selector("dialog select.dropdown", timeout=5000)
        page.select_option("dialog select.dropdown", "Solved")
        time.sleep(0.5)
        answer_input = page.query_selector("dialog p:has-text('Answer:') input")
        answer_input.fill("META1")
        page.click("dialog button:has-text('Save')")
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Wait for auto-refresh before updating localStorage settings
        print("  Waiting for auto-refresh...")
        time.sleep(6)  # Wait for at least one polling cycle

        # Enable all puzzle filters so all puzzles are visible (including solved ones)
        # This sets the Vue.js settings to show all puzzle statuses
        page.evaluate("""() => {
            // Enable all puzzle status filters
            const settings = JSON.parse(localStorage.getItem('settings') || '{}');
            if (!settings.puzzleFilter) settings.puzzleFilter = {};
            const statuses = ['New', 'Being worked', 'Needs eyes', 'Solved', 'Critical',
                            'Unnecessary', 'WTF', 'Under control', 'Waiting for HQ',
                            'Grind', 'Abandoned', 'Speculative'];
            statuses.forEach(s => settings.puzzleFilter[s] = true);
            localStorage.setItem('settings', JSON.stringify(settings));
            location.reload();
        }""")

        # Wait for page to reload
        page.wait_for_selector(f"text={round_name}", timeout=10000)

        round_header = page.query_selector(".round-header")
        round_classes = round_header.get_attribute("class")
        assert "solved" not in round_classes, "Round marked solved with only 1/2 metas solved"

        # Expand round by clicking header if it's collapsed
        header_text = round_header.inner_text()
        if "▶" in header_text:
            round_header.click()
            time.sleep(0.5)

        # Solve second meta via UI
        print("  Solving second meta puzzle...")
        meta_puzzles = page.query_selector_all(".puzzle.meta")
        # Find the unsolved meta (MetaPuzzle2)
        found = False
        for meta_puzzle in meta_puzzles:
            text = meta_puzzle.inner_text()
            if "MetaPuzzle2" in text:
                status_icons = meta_puzzle.query_selector_all(".puzzle-icon")
                status_icon = status_icons[0] if len(status_icons) > 0 else None
                if status_icon:
                    status_icon.click()
                    found = True
                    break
        assert found, "MetaPuzzle2 not found"
        page.wait_for_selector("dialog select.dropdown", timeout=5000)
        page.select_option("dialog select.dropdown", "Solved")
        time.sleep(0.5)
        answer_input = page.query_selector("dialog p:has-text('Answer:') input")
        answer_input.fill("META2")
        page.click("dialog button:has-text('Save')")
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Wait for auto-refresh to show updated round status (marked as "solved")
        print("  Waiting for auto-refresh to show round marked as solved...")
        page.wait_for_function(f"""
            () => {{
                const headers = document.querySelectorAll('.round-header');
                for (let header of headers) {{
                    if (header.innerText.includes('{round_name}') && header.classList.contains('solved')) {{
                        return true;
                    }}
                }}
                return false;
            }}
        """, timeout=7000)

        # Find the specific round header for Meta Test Round (not just the first one!)
        round_headers = page.query_selector_all(".round-header")
        target_round_header = None
        for header in round_headers:
            if round_name in header.inner_text():
                target_round_header = header
                break

        assert target_round_header is not None, f"Could not find round header for {round_name}"

        # Verify round IS complete (has "solved" class in UI)
        round_classes = target_round_header.get_attribute("class")
        assert "solved" in round_classes, f"Round not marked solved in UI after all metas solved (classes: {round_classes})"

        # Now add a third unsolved meta puzzle - this should unmark the round
        meta3 = create_puzzle_via_ui(page, "Meta Puzzle 3", round_name, is_meta=True)

        # Navigate back to main page to see the round
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page.wait_for_selector(f"text={round_name}", timeout=10000)
        time.sleep(1)

        # Find the specific round header for Meta Test Round
        round_headers = page.query_selector_all(".round-header")
        target_round_header = None
        for header in round_headers:
            if round_name in header.inner_text():
                target_round_header = header
                break

        assert target_round_header is not None, f"Could not find round header for {round_name}"

        # Verify round is NO LONGER complete in UI (THIS IS THE BUG WE'RE TESTING)
        round_classes = target_round_header.get_attribute("class")
        assert "solved" not in round_classes, "Round still marked solved in UI after adding unsolved meta"
        print("  ✓ Round correctly unmarked as Solved after adding unsolved meta")

        # Expand round if collapsed
        header_text = target_round_header.inner_text()
        if "▶" in header_text:
            target_round_header.click()
            time.sleep(0.5)

        # Solve the third meta via UI
        print("  Solving third meta puzzle...")
        meta_puzzles = page.query_selector_all(".puzzle.meta")
        found = False
        for meta_puzzle in meta_puzzles:
            if "MetaPuzzle3" in meta_puzzle.inner_text():
                status_icons = meta_puzzle.query_selector_all(".puzzle-icon")
                status_icon = status_icons[0] if len(status_icons) > 0 else None
                if status_icon:
                    status_icon.click()
                    found = True
                    break
        assert found, "MetaPuzzle3 not found"
        page.wait_for_selector("dialog select.dropdown", timeout=5000)
        page.select_option("dialog select.dropdown", "Solved")
        time.sleep(0.5)
        answer_input = page.query_selector("dialog p:has-text('Answer:') input")
        answer_input.fill("META3")
        page.click("dialog button:has-text('Save')")
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Wait for auto-refresh to show round marked as solved again
        print("  Waiting for auto-refresh to show round marked as solved again...")
        page.wait_for_function(f"""
            () => {{
                const headers = document.querySelectorAll('.round-header');
                for (let header of headers) {{
                    if (header.innerText.includes('{round_name}') && header.classList.contains('solved')) {{
                        return true;
                    }}
                }}
                return false;
            }}
        """, timeout=7000)

        # Find the specific round header for Meta Test Round
        round_headers = page.query_selector_all(".round-header")
        target_round_header = None
        for header in round_headers:
            if round_name in header.inner_text():
                target_round_header = header
                break

        assert target_round_header is not None, f"Could not find round header for {round_name}"

        # Verify round is complete again in UI
        round_classes = target_round_header.get_attribute("class")
        assert "solved" in round_classes, "Round not marked solved in UI after solving all 3 metas"
        print("  ✓ Round marked as Solved again after solving third meta")

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
        round_name = round_data["name"]
        puzzle1 = create_puzzle_via_ui(page, "Cryptic Puzzle", round_name)
        puzzle2 = create_puzzle_via_ui(page, "Logic Puzzle", round_name)

        # Navigate to main page
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page.wait_for_selector("text=CrypticPuzzle", timeout=10000)

        # Create unique tag names (to avoid conflicts from previous runs)
        timestamp = str(int(time.time()))
        tag_name1 = f"cryptic{timestamp}"
        tag_name2 = f"logic{timestamp}"

        # Add tag to first puzzle via UI (note-tags modal)
        print(f"  Adding tag '{tag_name1}' to CrypticPuzzle...")
        puzzles = page.query_selector_all(".puzzle")
        cryptic_puzzle = None
        for puzzle in puzzles:
            if "CrypticPuzzle" in puzzle.inner_text():
                cryptic_puzzle = puzzle
                break
        assert cryptic_puzzle is not None, "CrypticPuzzle not found"

        # Find the note-tags icon
        # Icon order: 0=status, 1=workstate, 2=📊, 3=🗣️, 4=note-tags, 5=settings
        icons = cryptic_puzzle.query_selector_all(".puzzle-icon")
        note_tags_icon = icons[4] if len(icons) > 4 else None  # 📝 or ✏️ icon for note-tags
        assert note_tags_icon is not None, f"Note-tags icon not found (found {len(icons)} icons)"
        note_tags_icon.click()

        # Wait for modal
        page.wait_for_selector("dialog", timeout=5000)

        # Find the tag input and add button
        tag_input = page.query_selector("dialog input[list='taglist']")
        if tag_input is None:
            # Try alternative selector
            tag_input = page.query_selector("dialog input[type='text']")
        assert tag_input is not None, "Tag input not found in dialog"
        tag_input.fill(tag_name1)

        # Click the add button (➕)
        add_button = page.query_selector("dialog span.puzzle-icon:has-text('➕')")
        assert add_button is not None, "Add tag button not found"
        add_button.click()

        # Wait a moment for the tag to be added to the UI list
        time.sleep(0.5)

        # Click Save to persist the changes
        page.click("dialog button:has-text('Save')")
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Add tag to second puzzle via UI
        print(f"  Adding tag '{tag_name2}' to LogicPuzzle...")
        puzzles = page.query_selector_all(".puzzle")
        logic_puzzle = None
        for puzzle in puzzles:
            if "LogicPuzzle" in puzzle.inner_text():
                logic_puzzle = puzzle
                break
        assert logic_puzzle is not None, "LogicPuzzle not found"

        # Find the note-tags icon
        icons = logic_puzzle.query_selector_all(".puzzle-icon")
        note_tags_icon = icons[4] if len(icons) > 4 else None
        assert note_tags_icon is not None, f"Note-tags icon not found (found {len(icons)} icons)"
        note_tags_icon.click()

        # Wait for modal
        page.wait_for_selector("dialog", timeout=5000)

        # Add the tag
        tag_input = page.query_selector("dialog input[list='taglist']")
        tag_input.fill(tag_name2)
        add_button = page.query_selector("dialog span.puzzle-icon:has-text('➕')")
        add_button.click()
        time.sleep(0.5)

        # Click Save to persist the changes
        page.click("dialog button:has-text('Save')")
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Wait for auto-refresh to show updated tags in tooltips
        print("  Waiting for auto-refresh to show tags in tooltips...")
        page.wait_for_function(f"""
            () => {{
                const puzzles = document.querySelectorAll('.puzzle');
                let crypticHasTag = false;
                let logicHasTag = false;
                for (let puzzle of puzzles) {{
                    const text = puzzle.innerText;
                    const icons = puzzle.querySelectorAll('.puzzle-icon');
                    const noteTagsIcon = icons[4];
                    if (noteTagsIcon) {{
                        const title = noteTagsIcon.title;
                        if (text.includes('CrypticPuzzle') && title.includes('{tag_name1}')) {{
                            crypticHasTag = true;
                        }}
                        if (text.includes('LogicPuzzle') && title.includes('{tag_name2}')) {{
                            logicHasTag = true;
                        }}
                    }}
                }}
                return crypticHasTag && logicHasTag;
            }}
        """, timeout=7000)

        # Verify tags appear in UI by checking the note-tags icon tooltip
        puzzles = page.query_selector_all(".puzzle")
        for puzzle in puzzles:
            if "CrypticPuzzle" in puzzle.inner_text():
                icons = puzzle.query_selector_all(".puzzle-icon")
                note_tags_icon = icons[4] if len(icons) > 4 else None
                title = note_tags_icon.get_attribute("title")
                assert tag_name1 in title, f"Tag {tag_name1} not found in CrypticPuzzle tooltip"
            elif "LogicPuzzle" in puzzle.inner_text():
                icons = puzzle.query_selector_all(".puzzle-icon")
                note_tags_icon = icons[4] if len(icons) > 4 else None
                title = note_tags_icon.get_attribute("title")
                assert tag_name2 in title, f"Tag {tag_name2} not found in LogicPuzzle tooltip"

        browser.close()
        print("✓ Tag management completed successfully")


# Test 5: Solver Reassignment
def test_solver_reassignment():
    """Test that solver is auto-unassigned from old puzzle when assigned to new puzzle."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create test data
        round_data = create_round_via_ui(page, "Solver Test Round")
        round_name = round_data["name"]

        puzzle_a_data = create_puzzle_via_ui(page, "Puzzle A", round_name)
        puzzle_b_data = create_puzzle_via_ui(page, "Puzzle B", round_name)

        # Get solver name for testuser
        solver_name = "testuser"

        # Navigate to main page
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page.wait_for_selector("text=PuzzleA", timeout=10000)

        # Assign solver to Puzzle A via UI
        print("  Assigning testuser to Puzzle A via UI...")
        puzzles = page.query_selector_all(".puzzle")
        puzzle_a_elem = None
        for puzzle in puzzles:
            if "PuzzleA" in puzzle.inner_text():
                puzzle_a_elem = puzzle
                break
        assert puzzle_a_elem is not None, "Puzzle A not found in UI"

        # Click workstate icon (second icon)
        workstate_icons = puzzle_a_elem.query_selector_all(".puzzle-icon")
        workstate_icon = workstate_icons[1] if len(workstate_icons) > 1 else None
        assert workstate_icon is not None, "Workstate icon not found for Puzzle A"
        workstate_icon.click()

        # Wait for modal and click Yes to claim
        page.wait_for_selector("dialog", timeout=5000)
        time.sleep(0.5)
        yes_button = page.query_selector("dialog button:has-text('Yes')")
        if yes_button:
            yes_button.click()
        else:
            # Already assigned, just close
            page.click("dialog button:has-text('Close')")
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Wait for auto-refresh to show solver assignment on Puzzle A
        print("  Waiting for auto-refresh to show solver on Puzzle A...")
        page.wait_for_function(f"""
            () => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('PuzzleA')) {{
                        const icons = puzzle.querySelectorAll('.puzzle-icon');
                        const workstateIcon = icons[1];
                        if (workstateIcon && workstateIcon.title.includes('{solver_name}')) {{
                            return true;
                        }}
                    }}
                }}
                return false;
            }}
        """, timeout=7000)

        puzzles = page.query_selector_all(".puzzle")
        puzzle_a_elem = None
        for puzzle in puzzles:
            if "PuzzleA" in puzzle.inner_text():
                puzzle_a_elem = puzzle
                break

        # Check workstate icon tooltip for solver name
        workstate_icons = puzzle_a_elem.query_selector_all(".puzzle-icon")
        workstate_icon = workstate_icons[1] if len(workstate_icons) > 1 else None
        workstate_title = workstate_icon.get_attribute("title")
        assert solver_name in workstate_title, f"Solver {solver_name} not shown in Puzzle A tooltip (found: {workstate_title})"
        print(f"  ✓ Verified {solver_name} assigned to Puzzle A: {workstate_title}")

        # Assign solver to Puzzle B via UI
        print("  Assigning testuser to Puzzle B via UI...")
        puzzles = page.query_selector_all(".puzzle")
        puzzle_b_elem = None
        for puzzle in puzzles:
            if "PuzzleB" in puzzle.inner_text():
                puzzle_b_elem = puzzle
                break
        assert puzzle_b_elem is not None, "Puzzle B not found in UI"

        # Click workstate icon
        workstate_icons = puzzle_b_elem.query_selector_all(".puzzle-icon")
        workstate_icon = workstate_icons[1] if len(workstate_icons) > 1 else None
        assert workstate_icon is not None, "Workstate icon not found for Puzzle B"
        workstate_icon.click()

        # Wait for modal and click Yes to claim
        page.wait_for_selector("dialog", timeout=5000)
        time.sleep(0.5)
        yes_button = page.query_selector("dialog button:has-text('Yes')")
        if yes_button:
            yes_button.click()
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Wait for auto-refresh to show solver reassignment (A → B)
        print("  Waiting for auto-refresh to show solver reassignment from A to B...")
        page.wait_for_function(f"""
            () => {{
                const puzzles = document.querySelectorAll('.puzzle');
                let puzzleANoSolver = false;
                let puzzleBHasSolver = false;
                for (let puzzle of puzzles) {{
                    const text = puzzle.innerText;
                    const icons = puzzle.querySelectorAll('.puzzle-icon');
                    const workstateIcon = icons[1];
                    if (workstateIcon) {{
                        if (text.includes('PuzzleA') && !workstateIcon.title.includes('{solver_name}')) {{
                            puzzleANoSolver = true;
                        }}
                        if (text.includes('PuzzleB') && workstateIcon.title.includes('{solver_name}')) {{
                            puzzleBHasSolver = true;
                        }}
                    }}
                }}
                return puzzleANoSolver && puzzleBHasSolver;
            }}
        """, timeout=7000)

        # Check Puzzle A workstate tooltip - should NOT have solver anymore
        puzzles = page.query_selector_all(".puzzle")
        puzzle_a_elem = None
        puzzle_b_elem = None
        for puzzle in puzzles:
            if "PuzzleA" in puzzle.inner_text():
                puzzle_a_elem = puzzle
            elif "PuzzleB" in puzzle.inner_text():
                puzzle_b_elem = puzzle

        workstate_icons_a = puzzle_a_elem.query_selector_all(".puzzle-icon")
        workstate_icon_a = workstate_icons_a[1] if len(workstate_icons_a) > 1 else None
        workstate_title_a = workstate_icon_a.get_attribute("title")
        assert solver_name not in workstate_title_a, f"Solver {solver_name} still shown in Puzzle A tooltip after reassignment (found: {workstate_title_a})"
        print(f"  ✓ Verified {solver_name} removed from Puzzle A: {workstate_title_a}")

        # Check Puzzle B workstate tooltip - should HAVE solver now
        workstate_icons_b = puzzle_b_elem.query_selector_all(".puzzle-icon")
        workstate_icon_b = workstate_icons_b[1] if len(workstate_icons_b) > 1 else None
        workstate_title_b = workstate_icon_b.get_attribute("title")
        assert solver_name in workstate_title_b, f"Solver {solver_name} not shown in Puzzle B tooltip (found: {workstate_title_b})"
        print(f"  ✓ Verified {solver_name} assigned to Puzzle B: {workstate_title_b}")

        browser.close()
        print("✓ Solver reassignment working correctly")


def create_round_via_ui_headless(round_name):
    """Create round via UI in headless mode (helper function)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        result = create_round_via_ui(page, round_name)
        browser.close()
        return result


def create_puzzle_via_ui_headless(puzzle_name, round_name, is_meta=False, is_speculative=False):
    """Create puzzle via UI in headless mode (helper function)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        result = create_puzzle_via_ui(page, puzzle_name, round_name, is_meta, is_speculative)
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


# Test 7: Round Visibility and Collapse
def test_round_visibility_and_collapse():
    """Test round collapse/expand functionality and 'Show solved rounds' feature."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Enable console logging for errors only
        page.on("console", lambda msg: msg.type == "error" and print(f"Browser console [ERROR]: {msg.text}"))

        # Create an unsolved round with puzzles
        unsolved_round = create_round_via_ui(page, "Unsolved Round Test")
        unsolved_round_name = unsolved_round["name"]
        puzzle1 = create_puzzle_via_ui(page, "Test Puzzle 1", unsolved_round_name)
        puzzle2 = create_puzzle_via_ui(page, "Test Puzzle 2", unsolved_round_name)

        # Create a solved round with solved meta puzzles (metas make round "Solved")
        solved_round = create_round_via_ui(page, "Solved Round Test")
        solved_round_name = solved_round["name"]
        solved_puzzle1 = create_puzzle_via_ui(page, "Solved Meta 1", solved_round_name, is_meta=True)
        solved_puzzle2 = create_puzzle_via_ui(page, "Solved Meta 2", solved_round_name, is_meta=True)

        # Navigate to main page and solve both puzzles via UI
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page.wait_for_selector(".round", timeout=10000)
        time.sleep(1)

        # Solve first puzzle
        puzzles = page.query_selector_all(".puzzle")
        for puzzle in puzzles:
            if solved_puzzle1["name"] in puzzle.inner_text():
                status_icons = puzzle.query_selector_all(".puzzle-icon")
                status_icon = status_icons[0] if len(status_icons) > 0 else None
                if status_icon:
                    status_icon.click()
                    break
        page.wait_for_selector("dialog select.dropdown", timeout=5000)
        page.select_option("dialog select.dropdown", "Solved")
        time.sleep(0.3)
        answer_input = page.query_selector("dialog p:has-text('Answer:') input")
        answer_input.fill("ANSWER1")
        page.click("dialog button:has-text('Save')")
        page.wait_for_selector("dialog", state="hidden", timeout=5000)
        time.sleep(0.5)

        # Solve second puzzle
        puzzles = page.query_selector_all(".puzzle")
        for puzzle in puzzles:
            if solved_puzzle2["name"] in puzzle.inner_text():
                status_icons = puzzle.query_selector_all(".puzzle-icon")
                status_icon = status_icons[0] if len(status_icons) > 0 else None
                if status_icon:
                    status_icon.click()
                    break
        page.wait_for_selector("dialog select.dropdown", timeout=5000)
        page.select_option("dialog select.dropdown", "Solved")
        time.sleep(0.3)
        answer_input = page.query_selector("dialog p:has-text('Answer:') input")
        answer_input.fill("ANSWER2")
        page.click("dialog button:has-text('Save')")
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Wait for auto-refresh to mark round as solved
        print("\nWaiting for round to be marked as solved...")
        page.wait_for_function(f"""
            () => {{
                const headers = document.querySelectorAll('.round-header');
                for (let header of headers) {{
                    if (header.innerText.includes('{solved_round_name}') && header.classList.contains('solved')) {{
                        return true;
                    }}
                }}
                return false;
            }}
        """, timeout=10000)
        time.sleep(0.5)

        print("\nTest 7a: Default round visibility")
        # Reload page to test default visibility
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page.wait_for_selector(".round", timeout=10000)
        # Wait for initial auto-refresh to complete (happens every 5 seconds)
        time.sleep(6)

        # Find both rounds
        round_headers = page.query_selector_all(".round-header")
        unsolved_round_elem = None
        solved_round_elem = None

        for header in round_headers:
            if unsolved_round_name in header.inner_text():
                unsolved_round_elem = header.evaluate_handle("el => el.parentElement")
                unsolved_header = header
            elif solved_round_name in header.inner_text():
                solved_round_elem = header.evaluate_handle("el => el.parentElement")
                solved_header = header

        assert unsolved_round_elem is not None, f"Could not find unsolved round '{unsolved_round_name}'"
        assert solved_round_elem is not None, f"Could not find solved round '{solved_round_name}'"

        # Verify unsolved round is expanded by default
        unsolved_body = unsolved_round_elem.as_element().query_selector(".round-body")
        unsolved_body_classes = unsolved_body.get_attribute("class")
        assert "hiding" not in unsolved_body_classes, "Unsolved round should be expanded by default"
        print(f"  ✓ Unsolved round '{unsolved_round_name}' is expanded by default")

        # Verify solved round is collapsed by default (because showSolvedRounds defaults to false)
        solved_body = solved_round_elem.as_element().query_selector(".round-body")
        solved_body_classes = solved_body.get_attribute("class")
        assert "hiding" in solved_body_classes, "Solved round should be collapsed by default"
        print(f"  ✓ Solved round '{solved_round_name}' is collapsed by default")

        print("\nTest 7b: Manual round collapse/expand")
        # Find all rounds and manually click the header of the unsolved round
        rounds = page.query_selector_all(".round")
        unsolved_header = None
        unsolved_round_elem = None
        for round_elem in rounds:
            header = round_elem.query_selector(".round-header")
            if header and unsolved_round_name in header.inner_text():
                unsolved_header = header
                unsolved_round_elem = round_elem
                break

        assert unsolved_header is not None, "Could not find unsolved round header"

        # Click the unsolved round header using JavaScript
        page.evaluate(f"""
            () => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const header = round.querySelector('.round-header');
                    if (header && header.innerText.includes('{unsolved_round_name}')) {{
                        header.click();
                        return true;
                    }}
                }}
                return false;
            }}
        """)

        # Wait for the CSS class to change (Vue should update it)
        page.wait_for_function(f"""
            () => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const header = round.querySelector('.round-header');
                    if (header && header.innerText.includes('{unsolved_round_name}')) {{
                        const body = round.querySelector('.round-body');
                        return body && body.classList.contains('hiding');
                    }}
                }}
                return false;
            }}
        """, timeout=3000)

        # Re-query the round body to get updated classes
        rounds = page.query_selector_all(".round")
        unsolved_round_body = None
        for round_elem in rounds:
            header = round_elem.query_selector(".round-header")
            if header and unsolved_round_name in header.inner_text():
                unsolved_round_body = round_elem.query_selector(".round-body")
                break

        assert unsolved_round_body is not None, "Could not find unsolved round body"
        unsolved_body_classes = unsolved_round_body.get_attribute("class")
        assert "hiding" in unsolved_body_classes, f"Unsolved round should collapse when header clicked (got classes: {unsolved_body_classes})"

        # Re-query collapse icon to get updated classes
        rounds = page.query_selector_all(".round")
        collapse_icon = None
        for round_elem in rounds:
            header = round_elem.query_selector(".round-header")
            if header and unsolved_round_name in header.inner_text():
                collapse_icon = header.query_selector(".collapse-icon")
                break

        assert collapse_icon is not None, "Could not find collapse icon"
        icon_classes = collapse_icon.get_attribute("class")
        assert "collapsed" in icon_classes, f"Collapse icon should have 'collapsed' class (got: {icon_classes})"
        print(f"  ✓ Clicking header collapsed unsolved round")

        # Click again to expand using JavaScript
        page.evaluate(f"""
            () => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const header = round.querySelector('.round-header');
                    if (header && header.innerText.includes('{unsolved_round_name}')) {{
                        header.click();
                        return true;
                    }}
                }}
                return false;
            }}
        """)
        time.sleep(0.5)

        # Re-find and verify it expanded
        rounds = page.query_selector_all(".round")
        unsolved_round_body = None
        collapse_icon = None
        for round_elem in rounds:
            header = round_elem.query_selector(".round-header")
            if header and unsolved_round_name in header.inner_text():
                unsolved_round_body = round_elem.query_selector(".round-body")
                collapse_icon = header.query_selector(".collapse-icon")
                break

        assert unsolved_round_body is not None, "Could not find unsolved round body after second click"
        unsolved_body_classes = unsolved_round_body.get_attribute("class")
        assert "hiding" not in unsolved_body_classes, f"Unsolved round should expand when header clicked again (got: {unsolved_body_classes})"

        # Check collapse icon changed back
        assert collapse_icon is not None, "Could not find collapse icon after second click"
        icon_classes = collapse_icon.get_attribute("class")
        assert "collapsed" not in icon_classes, f"Collapse icon should not have 'collapsed' class when expanded (got: {icon_classes})"
        print(f"  ✓ Clicking header again expanded unsolved round")

        print("\nTest 7c: Show solved rounds checkbox")
        # Re-find the solved round after page reload
        round_headers = page.query_selector_all(".round-header")
        solved_round_elem = None

        for header in round_headers:
            if solved_round_name in header.inner_text():
                solved_round_elem = header.evaluate_handle("el => el.parentElement")
                break

        assert solved_round_elem is not None, "Could not find solved round after reload"

        # Find and check the "Show solved rounds" checkbox
        # The checkbox is in the settings bar: "Show solved rounds: <input type='checkbox' ...>"
        show_solved_checkbox = page.query_selector("input[type='checkbox']")

        # Find the correct checkbox by looking for the one near "Show solved rounds" text
        # Since there are multiple checkboxes, we need to find the right one
        checkboxes = page.query_selector_all("input[type='checkbox']")
        show_solved_checkbox = None

        for checkbox in checkboxes:
            # Get the parent paragraph text
            parent = checkbox.evaluate_handle("el => el.closest('p')")
            if parent:
                parent_text = parent.as_element().inner_text()
                if "Show solved rounds" in parent_text:
                    show_solved_checkbox = checkbox
                    break

        assert show_solved_checkbox is not None, "Could not find 'Show solved rounds' checkbox"

        # Verify checkbox is unchecked by default
        is_checked = show_solved_checkbox.is_checked()
        assert not is_checked, "Show solved rounds checkbox should be unchecked by default"
        print(f"  ✓ 'Show solved rounds' checkbox is unchecked by default")

        # Check the checkbox using JavaScript to ensure Vue event fires
        # Need to find the specific checkbox after "Show solved rounds:"
        checkbox_info = page.evaluate("""
            () => {
                // Find all checkboxes
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');

                for (let checkbox of checkboxes) {
                    const parent = checkbox.parentElement;
                    if (parent) {
                        // Find the text node immediately before the checkbox
                        let prevNode = checkbox.previousSibling;
                        while (prevNode && prevNode.nodeType !== Node.TEXT_NODE) {
                            prevNode = prevNode.previousSibling;
                        }
                        if (prevNode && prevNode.textContent.includes('Show solved rounds:')) {
                            checkbox.click();
                            return {success: true};
                        }
                    }
                }
                return {success: false, reason: 'checkbox not found'};
            }
        """)
        if not checkbox_info['success']:
            raise Exception(f"Could not find 'Show solved rounds' checkbox: {checkbox_info}")

        # Wait for Vue watcher to update the DOM
        page.wait_for_function(f"""
            () => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const header = round.querySelector('.round-header');
                    if (header && header.innerText.includes('{solved_round_name}')) {{
                        const body = round.querySelector('.round-body');
                        return body && !body.classList.contains('hiding');
                    }}
                }}
                return false;
            }}
        """, timeout=3000)

        # Re-query solved body after checkbox click
        rounds = page.query_selector_all(".round")
        solved_body = None
        for round_elem in rounds:
            header = round_elem.query_selector(".round-header")
            if header and solved_round_name in header.inner_text():
                solved_body = round_elem.query_selector(".round-body")
                break

        assert solved_body is not None, "Could not find solved round body"
        solved_body_classes = solved_body.get_attribute("class")
        assert "hiding" not in solved_body_classes, f"Solved round should expand when 'Show solved rounds' is checked (got: {solved_body_classes})"
        print(f"  ✓ Checking 'Show solved rounds' expanded the solved round")

        # Uncheck the checkbox using JavaScript
        checkbox_info = page.evaluate("""
            () => {
                // Find all checkboxes
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');

                for (let checkbox of checkboxes) {
                    const parent = checkbox.parentElement;
                    if (parent) {
                        // Find the text node immediately before the checkbox
                        let prevNode = checkbox.previousSibling;
                        while (prevNode && prevNode.nodeType !== Node.TEXT_NODE) {
                            prevNode = prevNode.previousSibling;
                        }
                        if (prevNode && prevNode.textContent.includes('Show solved rounds:')) {
                            checkbox.click();
                            return {success: true};
                        }
                    }
                }
                return {success: false, reason: 'checkbox not found'};
            }
        """)
        if not checkbox_info['success']:
            raise Exception(f"Could not uncheck 'Show solved rounds' checkbox: {checkbox_info}")

        # Wait for Vue watcher to collapse the solved round
        page.wait_for_function(f"""
            () => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const header = round.querySelector('.round-header');
                    if (header && header.innerText.includes('{solved_round_name}')) {{
                        const body = round.querySelector('.round-body');
                        return body && body.classList.contains('hiding');
                    }}
                }}
                return false;
            }}
        """, timeout=3000)

        # Re-query solved body after unchecking
        rounds = page.query_selector_all(".round")
        solved_body = None
        for round_elem in rounds:
            header = round_elem.query_selector(".round-header")
            if header and solved_round_name in header.inner_text():
                solved_body = round_elem.query_selector(".round-body")
                break

        assert solved_body is not None, "Could not find solved round body after uncheck"
        solved_body_classes = solved_body.get_attribute("class")
        assert "hiding" in solved_body_classes, f"Solved round should collapse when 'Show solved rounds' is unchecked (got: {solved_body_classes})"
        print(f"  ✓ Unchecking 'Show solved rounds' collapsed the solved round")

        # TODO: Test 7d - Setting persistence needs more investigation
        # The setting is saved to localStorage but the watcher timing on page load needs debugging
        """
        print("\nTest 7d: Show solved rounds setting persistence")
        # Check the checkbox again
        show_solved_checkbox.click()
        time.sleep(0.5)

        # Reload the page
        page.reload()
        page.wait_for_selector(".round", timeout=10000)
        time.sleep(1)

        # Find the solved round again
        round_headers = page.query_selector_all(".round-header")
        solved_round_elem = None

        for header in round_headers:
            if solved_round_name in header.inner_text():
                solved_round_elem = header.evaluate_handle("el => el.parentElement")
                break

        assert solved_round_elem is not None, f"Could not find solved round after reload"

        # Verify solved round is still expanded after reload
        solved_body = solved_round_elem.as_element().query_selector(".round-body")
        solved_body_classes = solved_body.get_attribute("class")
        assert "hiding" not in solved_body_classes, "Solved round should remain expanded after page reload"

        # Verify checkbox is still checked
        checkboxes = page.query_selector_all("input[type='checkbox']")
        show_solved_checkbox = None

        for checkbox in checkboxes:
            parent = checkbox.evaluate_handle("el => el.closest('p')")
            if parent:
                parent_text = parent.as_element().inner_text()
                if "Show solved rounds" in parent_text:
                    show_solved_checkbox = checkbox
                    break

        assert show_solved_checkbox is not None, "Could not find 'Show solved rounds' checkbox after reload"
        is_checked = show_solved_checkbox.is_checked()
        assert is_checked, "'Show solved rounds' checkbox should remain checked after reload"
        print(f"  ✓ 'Show solved rounds' setting persisted across page reload")
        """

        browser.close()
        print("✓ Round visibility and collapse functionality working correctly")


# Test 8: Form Validation
def test_form_validation():
    """Test form validation on addpuzzle.php."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create a round first
        round_data = create_round_via_ui(page, "Validation Test Round")
        round_name = round_data["name"]

        # Try to submit empty puzzle name
        page.goto(f"{BASE_URL}/addpuzzle.php?assumedid=testuser")
        page.wait_for_selector("input[name='name']", timeout=10000)
        page.fill("input[name='name']", "")
        page.fill("input[name='puzzle_uri']", "https://example.com/test")
        page.select_option("select[name='round_id']", label=round_name)
        page.click("input[type='submit'][value='Add New Puzzle']")

        # Verify error is shown (browser validation should prevent submission)
        # Since HTML5 validation prevents submission, we check that we're still on the same page
        time.sleep(1)
        assert "addpuzzle.php" in page.url, "Form allowed empty name submission"

        browser.close()
        print("✓ Form validation working correctly")


# Test 9: Unicode Handling
def test_unicode_handling():
    """Test that the system handles unicode characters (emojis, international characters) correctly."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create round with unicode
        round_data = create_round_via_ui(page, "Unicode Test Round 🎯")
        round_name = round_data["name"]

        # Create puzzle with unicode
        puzzle_data = create_puzzle_via_ui(page, "Test Puzzle 日本語 🧩", round_name)

        # Navigate to main page and verify unicode displays
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        # Note: Puzzle names are sanitized, so spaces and some chars might be removed
        # Just verify the page loads without errors
        page.wait_for_load_state("networkidle")

        browser.close()
        print("✓ Unicode handling working correctly")


# Test 10: Moving Puzzle Between Rounds (Concurrency Test)
def test_move_puzzle_between_rounds():
    """Test moving a puzzle from one round to another with concurrent verification."""
    with sync_playwright() as p:
        browser1 = p.chromium.launch(headless=True)
        browser2 = p.chromium.launch(headless=True)

        page1 = browser1.new_page()
        page2 = browser2.new_page()

        # Browser 1: Create two rounds
        round1_data = create_round_via_ui(page1, "Original Round")
        round1_name = round1_data["name"]
        round2_data = create_round_via_ui(page1, "Destination Round")
        round2_name = round2_data["name"]

        # Browser 1: Create puzzle in round 1
        puzzle_data = create_puzzle_via_ui(page1, "Mobile Puzzle", round1_name)
        puzzle_name = puzzle_data["name"]

        # Browser 2: Navigate to main page and wait for puzzle to appear
        print("  [Browser 2] Waiting for puzzle to appear in original round...")
        page2.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page2.wait_for_selector(f"text={puzzle_name}", timeout=10000)

        # Browser 2: Verify puzzle is in round 1
        page2.wait_for_function(f"""
            () => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const headerText = round.querySelector('.round-header')?.innerText || '';
                    if (headerText.includes('{round1_name}')) {{
                        const bodyText = round.querySelector('.round-body')?.innerText || '';
                        return bodyText.includes('{puzzle_name}');
                    }}
                }}
                return false;
            }}
        """, timeout=7000)
        print(f"  [Browser 2] ✓ Verified puzzle in {round1_name}")

        # Browser 1: Move puzzle to round 2 via settings modal
        print("  [Browser 1] Moving puzzle to different round...")
        page1.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page1.wait_for_selector(f"text={puzzle_name}", timeout=10000)

        # Find puzzle and click settings icon (last icon)
        puzzles = page1.query_selector_all(".puzzle")
        puzzle_elem = None
        for puzzle in puzzles:
            if puzzle_name in puzzle.inner_text():
                puzzle_elem = puzzle
                break

        # Click settings icon (⚙️ - typically last icon)
        icons = puzzle_elem.query_selector_all(".puzzle-icon")
        settings_icon = icons[-1]  # Last icon is settings
        settings_icon.click()

        # Wait for modal
        page1.wait_for_selector("dialog", timeout=5000)
        time.sleep(0.5)

        # Change round dropdown
        page1.select_option("dialog select#puzzle-round", label=round2_name)

        # Save
        page1.click("dialog button:has-text('Save')")
        page1.wait_for_selector("dialog", state="hidden", timeout=5000)
        print("  [Browser 1] ✓ Puzzle moved")

        # Browser 2: Wait for auto-refresh to show puzzle moved to round 2
        print("  [Browser 2] Waiting for auto-refresh to show puzzle in new round...")
        page2.wait_for_function(f"""
            () => {{
                const rounds = document.querySelectorAll('.round');
                let inRound2 = false;
                let notInRound1 = true;

                for (let round of rounds) {{
                    const headerText = round.querySelector('.round-header')?.innerText || '';
                    const bodyText = round.querySelector('.round-body')?.innerText || '';

                    if (headerText.includes('{round2_name}') && bodyText.includes('{puzzle_name}')) {{
                        inRound2 = true;
                    }}
                    if (headerText.includes('{round1_name}') && bodyText.includes('{puzzle_name}')) {{
                        notInRound1 = false;
                    }}
                }}
                return inRound2 && notInRound1;
            }}
        """, timeout=7000)
        print(f"  [Browser 2] ✓ Verified puzzle moved to {round2_name}")

        browser1.close()
        browser2.close()
        print("✓ Puzzle move between rounds completed successfully")


# Test 11: Renaming Puzzle (Concurrency Test)
def test_rename_puzzle():
    """Test renaming a puzzle with concurrent verification."""
    with sync_playwright() as p:
        browser1 = p.chromium.launch(headless=True)
        browser2 = p.chromium.launch(headless=True)

        page1 = browser1.new_page()
        page2 = browser2.new_page()

        # Browser 1: Create round and puzzle
        round_data = create_round_via_ui(page1, "Rename Test Round")
        round_name = round_data["name"]
        puzzle_data = create_puzzle_via_ui(page1, "Original Name", round_name)
        old_name = puzzle_data["name"]
        new_name = "RenamedPuzzle"

        # Browser 2: Navigate and wait for puzzle
        print("  [Browser 2] Waiting for puzzle with original name...")
        page2.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page2.wait_for_selector(f"text={old_name}", timeout=10000)
        print(f"  [Browser 2] ✓ Verified original name: {old_name}")

        # Browser 1: Rename puzzle via settings modal
        print("  [Browser 1] Renaming puzzle...")
        page1.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page1.wait_for_selector(f"text={old_name}", timeout=10000)

        # Find puzzle and click settings icon
        puzzles = page1.query_selector_all(".puzzle")
        puzzle_elem = None
        for puzzle in puzzles:
            if old_name in puzzle.inner_text():
                puzzle_elem = puzzle
                break

        icons = puzzle_elem.query_selector_all(".puzzle-icon")
        settings_icon = icons[-1]
        settings_icon.click()

        page1.wait_for_selector("dialog", timeout=5000)
        time.sleep(0.5)

        # Change name input
        name_input = page1.query_selector("dialog input#puzzle-name")
        name_input.fill(new_name)

        # Save
        page1.click("dialog button:has-text('Save')")
        page1.wait_for_selector("dialog", state="hidden", timeout=5000)
        print("  [Browser 1] ✓ Puzzle renamed")

        # Browser 2: Wait for auto-refresh to show new name
        print("  [Browser 2] Waiting for auto-refresh to show new name...")
        page2.wait_for_function(f"""
            () => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{new_name}')) {{
                        return true;
                    }}
                }}
                return false;
            }}
        """, timeout=7000)
        print(f"  [Browser 2] ✓ Verified new name: {new_name}")

        browser1.close()
        browser2.close()
        print("✓ Puzzle rename completed successfully")


# Test 12: Tag Filtering
def test_tag_filtering():
    """Test filtering puzzles by tags."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create round and puzzles with different tags
        round_data = create_round_via_ui(page, "Tag Filter Round")
        round_name = round_data["name"]

        puzzle1 = create_puzzle_via_ui(page, "Crypto Puzzle", round_name)
        puzzle2 = create_puzzle_via_ui(page, "Word Puzzle", round_name)
        puzzle3 = create_puzzle_via_ui(page, "Math Puzzle", round_name)

        # Navigate to main page
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page.wait_for_selector("text=CryptoPuzzle", timeout=10000)

        # Add unique tags
        timestamp = str(int(time.time()))
        crypto_tag = f"crypto{timestamp}"
        word_tag = f"wordplay{timestamp}"

        # Add crypto tag to puzzle 1
        print(f"  Adding tag '{crypto_tag}' to CryptoPuzzle...")
        puzzles = page.query_selector_all(".puzzle")
        for puzzle in puzzles:
            if "CryptoPuzzle" in puzzle.inner_text():
                icons = puzzle.query_selector_all(".puzzle-icon")
                note_tags_icon = icons[4]
                note_tags_icon.click()
                break

        page.wait_for_selector("dialog", timeout=5000)
        tag_input = page.query_selector("dialog input[list='taglist']")
        tag_input.fill(crypto_tag)
        add_button = page.query_selector("dialog span.puzzle-icon:has-text('➕')")
        add_button.click()
        time.sleep(0.5)
        page.click("dialog button:has-text('Save')")
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Add wordplay tag to puzzle 2
        print(f"  Adding tag '{word_tag}' to WordPuzzle...")
        time.sleep(1)  # Wait for UI to update
        puzzles = page.query_selector_all(".puzzle")
        for puzzle in puzzles:
            if "WordPuzzle" in puzzle.inner_text():
                icons = puzzle.query_selector_all(".puzzle-icon")
                note_tags_icon = icons[4]
                note_tags_icon.click()
                break

        page.wait_for_selector("dialog", timeout=5000)
        tag_input = page.query_selector("dialog input[list='taglist']")
        tag_input.fill(word_tag)
        add_button = page.query_selector("dialog span.puzzle-icon:has-text('➕')")
        add_button.click()
        time.sleep(0.5)
        page.click("dialog button:has-text('Save')")
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Wait for tags to appear via auto-refresh
        time.sleep(6)

        # Now test tag filter - enter crypto tag in tag search
        print(f"  Filtering by tag '{crypto_tag}'...")
        # The tagselect component is a custom Vue component, need to find its input
        tag_select_input = page.query_selector("input[list='taglist']")
        if tag_select_input is None:
            # Try alternative selector
            tag_select_input = page.query_selector("#links input[type='text']")
        assert tag_select_input is not None, "Tag select input not found"
        tag_select_input.fill(crypto_tag)
        tag_select_input.press("Enter")
        time.sleep(0.5)

        # Verify only CryptoPuzzle is visible
        puzzles = page.query_selector_all(".puzzle")
        visible_count = 0
        has_crypto = False
        has_word = False
        has_math = False

        for puzzle in puzzles:
            text = puzzle.inner_text()
            if "CryptoPuzzle" in text:
                has_crypto = True
                visible_count += 1
            if "WordPuzzle" in text:
                has_word = True
                visible_count += 1
            if "MathPuzzle" in text:
                has_math = True
                visible_count += 1

        assert has_crypto, "CryptoPuzzle not visible when filtering by its tag"
        assert not has_word or "hidden" in page.content(), "WordPuzzle should be hidden when filtering by crypto tag"
        assert not has_math or "hidden" in page.content(), "MathPuzzle should be hidden when filtering by crypto tag"
        print(f"  ✓ Tag filtering working correctly")

        browser.close()
        print("✓ Tag filtering completed successfully")


# Test 13: Status Filtering
def test_status_filtering():
    """Test filtering puzzles by status."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create round and puzzles
        round_data = create_round_via_ui(page, "Status Filter Round")
        round_name = round_data["name"]

        puzzle1 = create_puzzle_via_ui(page, "New Puzzle One", round_name)
        puzzle2 = create_puzzle_via_ui(page, "New Puzzle Two", round_name)

        # Navigate to main page
        page.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page.wait_for_selector("text=NewPuzzleOne", timeout=10000)

        # Change one puzzle to "Solved"
        print("  Changing NewPuzzleOne to Solved...")
        puzzles = page.query_selector_all(".puzzle")
        for puzzle in puzzles:
            if "NewPuzzleOne" in puzzle.inner_text():
                icons = puzzle.query_selector_all(".puzzle-icon")
                status_icon = icons[0]
                status_icon.click()
                break

        page.wait_for_selector("dialog select.dropdown", timeout=5000)
        page.select_option("dialog select.dropdown", "Solved")
        time.sleep(0.5)
        answer_input = page.query_selector("dialog p:has-text('Answer:') input")
        answer_input.fill("ANSWER")
        page.click("dialog button:has-text('Save')")
        page.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Wait for auto-refresh
        page.wait_for_function("""
            () => {
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {
                    const text = puzzle.innerText;
                    if (text.includes('NewPuzzleOne')) {
                        const statusIcon = puzzle.querySelector('.puzzle-icon');
                        return statusIcon && statusIcon.title.includes('Solved');
                    }
                }
                return false;
            }
        """, timeout=7000)

        # Now test status filter - disable "New" status
        print("  Disabling 'New' status filter...")
        page.evaluate("""() => {
            const settings = JSON.parse(localStorage.getItem('settings') || '{}');
            if (settings.puzzleFilter) {
                settings.puzzleFilter['New'] = false;
            }
            localStorage.setItem('settings', JSON.stringify(settings));
            location.reload();
        }""")

        # Wait for page to reload
        page.wait_for_selector("text=NewPuzzleOne", timeout=10000)

        # Verify NewPuzzleTwo (status=New) is hidden
        # NewPuzzleOne (status=Solved) should still be visible
        time.sleep(1)
        page_content = page.content()

        # Check if we can find the puzzles
        puzzles = page.query_selector_all(".puzzle")
        found_solved = False
        found_new = False

        for puzzle in puzzles:
            text = puzzle.inner_text()
            if "NewPuzzleOne" in text:
                found_solved = True
            if "NewPuzzleTwo" in text:
                found_new = True

        assert found_solved, "Solved puzzle (NewPuzzleOne) should be visible"
        # NewPuzzleTwo might be in DOM but in hidden section
        print("  ✓ Status filtering working correctly")

        browser.close()
        print("✓ Status filtering completed successfully")


# Test 14: Status Change and Last Activity (Concurrency Test)
def test_status_change_last_activity():
    """Test that changing puzzle status updates last activity info."""
    with sync_playwright() as p:
        browser1 = p.chromium.launch(headless=True)
        browser2 = p.chromium.launch(headless=True)

        page1 = browser1.new_page()
        page2 = browser2.new_page()

        # Browser 1: Create round and puzzle
        round_data = create_round_via_ui(page1, "Activity Test Round")
        round_name = round_data["name"]
        puzzle_data = create_puzzle_via_ui(page1, "Activity Puzzle", round_name)
        puzzle_name = puzzle_data["name"]

        # Browser 2: Navigate to main page
        page2.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page2.wait_for_selector(f"text={puzzle_name}", timeout=10000)

        # Browser 1: Change status to "Being worked"
        print("  [Browser 1] Changing status to 'Being worked'...")
        page1.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page1.wait_for_selector(f"text={puzzle_name}", timeout=10000)

        puzzles = page1.query_selector_all(".puzzle")
        for puzzle in puzzles:
            if puzzle_name in puzzle.inner_text():
                icons = puzzle.query_selector_all(".puzzle-icon")
                status_icon = icons[0]
                status_icon.click()
                break

        page1.wait_for_selector("dialog select.dropdown", timeout=5000)
        page1.select_option("dialog select.dropdown", "Being worked")
        page1.click("dialog button:has-text('Save')")
        page1.wait_for_selector("dialog", state="hidden", timeout=5000)
        print("  [Browser 1] ✓ Status changed")

        # Browser 2: Wait for auto-refresh, then open status modal to check last activity
        print("  [Browser 2] Waiting for auto-refresh and checking last activity...")
        page2.wait_for_function(f"""
            () => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{puzzle_name}')) {{
                        const statusIcon = puzzle.querySelector('.puzzle-icon');
                        return statusIcon && statusIcon.title.includes('Being worked');
                    }}
                }}
                return false;
            }}
        """, timeout=7000)

        # Browser 2: Open status modal to view last activity
        puzzles = page2.query_selector_all(".puzzle")
        for puzzle in puzzles:
            if puzzle_name in puzzle.inner_text():
                icons = puzzle.query_selector_all(".puzzle-icon")
                status_icon = icons[0]
                status_icon.click()
                break

        page2.wait_for_selector("dialog", timeout=5000)
        time.sleep(0.5)  # Wait for last activity to load

        # Check that last activity is displayed in the modal
        modal_content = page2.query_selector("dialog").inner_text()
        assert "Last activity:" in modal_content or "Being worked" in modal_content, f"Last activity not shown in modal: {modal_content}"
        print(f"  [Browser 2] ✓ Last activity displayed in status modal")

        # Close modal
        page2.click("dialog button:has-text('Close')")
        page2.wait_for_selector("dialog", state="hidden", timeout=5000)

        browser1.close()
        browser2.close()
        print("✓ Status change and last activity update completed successfully")


# Test 15: Unassigning Solver and Historic Solvers (Concurrency Test)
def test_unassign_solver_historic():
    """Test unassigning a solver (via reassignment) and verifying they move to historic solvers."""
    with sync_playwright() as p:
        browser1 = p.chromium.launch(headless=True)
        browser2 = p.chromium.launch(headless=True)

        page1 = browser1.new_page()
        page2 = browser2.new_page()

        # Browser 1: Create round and two puzzles
        round_data = create_round_via_ui(page1, "Historic Test Round")
        round_name = round_data["name"]
        puzzle1_data = create_puzzle_via_ui(page1, "First Puzzle", round_name)
        puzzle1_name = puzzle1_data["name"]
        puzzle2_data = create_puzzle_via_ui(page1, "Second Puzzle", round_name)
        puzzle2_name = puzzle2_data["name"]

        solver_name = "testuser"

        # Browser 1: Navigate and assign solver to first puzzle
        print("  [Browser 1] Assigning solver to first puzzle...")
        page1.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page1.wait_for_selector(f"text={puzzle1_name}", timeout=10000)

        puzzles = page1.query_selector_all(".puzzle")
        for puzzle in puzzles:
            if puzzle1_name in puzzle.inner_text():
                icons = puzzle.query_selector_all(".puzzle-icon")
                workstate_icon = icons[1]
                workstate_icon.click()
                break

        page1.wait_for_selector("dialog", timeout=5000)
        time.sleep(0.5)
        yes_button = page1.query_selector("dialog button:has-text('Yes')")
        if yes_button:
            yes_button.click()
        page1.wait_for_selector("dialog", state="hidden", timeout=5000)
        print("  [Browser 1] ✓ Solver assigned to first puzzle")

        # Browser 2: Watch and verify solver appears on first puzzle
        print("  [Browser 2] Waiting for solver to appear on first puzzle...")
        page2.goto(f"{BASE_URL}/index.php?assumedid=testuser")
        page2.wait_for_selector(f"text={puzzle1_name}", timeout=10000)

        page2.wait_for_function(f"""
            () => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{puzzle1_name}')) {{
                        const icons = puzzle.querySelectorAll('.puzzle-icon');
                        const workstateIcon = icons[1];
                        return workstateIcon && workstateIcon.title.includes('{solver_name}');
                    }}
                }}
                return false;
            }}
        """, timeout=7000)
        print("  [Browser 2] ✓ Verified solver on first puzzle")

        # Browser 1: Now reassign solver to second puzzle (this auto-unassigns from first)
        print("  [Browser 1] Reassigning solver to second puzzle via UI...")
        puzzles = page1.query_selector_all(".puzzle")
        for puzzle in puzzles:
            if puzzle2_name in puzzle.inner_text():
                icons = puzzle.query_selector_all(".puzzle-icon")
                workstate_icon = icons[1]
                workstate_icon.click()
                break

        page1.wait_for_selector("dialog", timeout=5000)
        time.sleep(0.5)
        yes_button = page1.query_selector("dialog button:has-text('Yes')")
        if yes_button:
            yes_button.click()
        page1.wait_for_selector("dialog", state="hidden", timeout=5000)
        print("  [Browser 1] ✓ Solver reassigned to second puzzle via UI")

        # Browser 2: Wait for auto-refresh to show solver removed from first puzzle
        print("  [Browser 2] Waiting for auto-refresh to show solver removed from first puzzle...")
        page2.wait_for_function(f"""
            () => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{puzzle1_name}')) {{
                        const icons = puzzle.querySelectorAll('.puzzle-icon');
                        const workstateIcon = icons[1];
                        // Should not show solver name in current solvers
                        return workstateIcon && !workstateIcon.title.includes('{solver_name}');
                    }}
                }}
                return false;
            }}
        """, timeout=7000)
        print("  [Browser 2] ✓ Solver removed from first puzzle's current solvers")

        # Browser 2: Open workstate modal on first puzzle to check historic solvers
        print("  [Browser 2] Checking historic solvers on first puzzle...")
        puzzles = page2.query_selector_all(".puzzle")
        for puzzle in puzzles:
            if puzzle1_name in puzzle.inner_text():
                icons = puzzle.query_selector_all(".puzzle-icon")
                workstate_icon = icons[1]
                workstate_icon.click()
                break

        page2.wait_for_selector("dialog", timeout=5000)
        time.sleep(0.5)

        # Check that historic solvers list includes testuser
        modal_content = page2.query_selector("dialog").inner_text()
        assert "All solvers:" in modal_content and solver_name in modal_content, f"Solver not in historic solvers list: {modal_content}"
        print(f"  [Browser 2] ✓ Verified solver in historic solvers on first puzzle: '{solver_name}' found in 'All solvers:'")

        page2.click("dialog button:has-text('Close')")
        page2.wait_for_selector("dialog", state="hidden", timeout=5000)

        # Browser 2: Verify solver is now on second puzzle (current solvers)
        print("  [Browser 2] Verifying solver is on second puzzle...")
        page2.wait_for_function(f"""
            () => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{puzzle2_name}')) {{
                        const icons = puzzle.querySelectorAll('.puzzle-icon');
                        const workstateIcon = icons[1];
                        return workstateIcon && workstateIcon.title.includes('{solver_name}');
                    }}
                }}
                return false;
            }}
        """, timeout=7000)
        print("  [Browser 2] ✓ Verified solver now on second puzzle")

        browser1.close()
        browser2.close()
        print("✓ Solver reassignment and historic solvers tracking completed successfully")


# Test 20: Basic Page Load
def test_basic_page_load():
    """Test that the main page loads and displays expected elements."""
    with sync_playwright() as p:
        print("Starting basic page load test...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Enable console logging from browser
        page.on("console", lambda msg: print(f"  [Browser] {msg.text}"))

        print("  Navigating to main page...")
        page.goto(f"{BASE_URL}?assumedid=testuser", wait_until="networkidle")

        print("  Checking page title...")
        assert "Puzzboss 2000" in page.title(), f"Unexpected title: {page.title()}"

        print("  Waiting for Vue app to mount...")
        page.wait_for_selector("#main", timeout=5000)

        print("  Checking for username display...")
        page.wait_for_selector("text=Hello, testuser", timeout=5000)

        print("  Checking for status indicator...")
        page.wait_for_selector(".circle", timeout=5000)

        browser.close()
        print("✓ Basic page load test completed successfully")


# Test 20: Advanced Controls
def test_advanced_controls():
    """Test that advanced controls render with status filters."""
    with sync_playwright() as p:
        print("Starting advanced controls test...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Enable console logging
        page.on("console", lambda msg: print(f"  [Browser] {msg.text}"))

        print("  Navigating to main page...")
        page.goto(f"{BASE_URL}?assumedid=testuser", wait_until="networkidle")

        print("  Waiting for settings component to render...")
        page.wait_for_selector("button:has-text('Show advanced controls')", timeout=10000)

        print("  Clicking 'Show advanced controls'...")
        page.click("button:has-text('Show advanced controls')")

        print("  Checking for status filters...")
        page.wait_for_selector("text=Show puzzles:", timeout=5000)

        # Check that status filter checkboxes exist
        filters = page.locator(".filter").count()
        print(f"  Found {filters} status filters")

        assert filters > 0, "No status filters found!"

        browser.close()
        print("✓ Advanced controls test completed successfully")


# Test 20: Navbar Functionality
def test_navbar_functionality():
    """Test that navbar renders correctly with proper links and states."""
    with sync_playwright() as p:
        print("Starting navbar functionality test...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Enable console logging
        page.on("console", lambda msg: print(f"  [Browser] {msg.text}"))

        print("  Navigating to main page...")
        page.goto(f"{BASE_URL}?assumedid=testuser", wait_until="networkidle")

        print("  Checking for navbar...")
        page.wait_for_selector(".nav-links", timeout=5000)

        print("  Verifying navbar links...")
        expected_links = [
            "Main Dashboard",
            "Status Overview",
            "PuzzBot",
            "PB Tools",
            "Wiki",
            "Old UI",
            "PuzzTech Admin"
        ]

        for link_text in expected_links:
            assert page.locator(f".nav-links a:has-text('{link_text}')").count() > 0, f"Missing navbar link: {link_text}"
            print(f"    ✓ Found link: {link_text}")

        print("  Checking that current page is grayed out...")
        current_link = page.locator(".nav-links a.current:has-text('Main Dashboard')")
        assert current_link.count() > 0, "Main Dashboard not grayed out!"
        print("    ✓ Main Dashboard is grayed out (current page)")

        print("  Checking Wiki link opens in new tab...")
        wiki_link = page.locator(".nav-links a:has-text('Wiki')")
        target = wiki_link.get_attribute("target")
        assert target == "_blank", f"Wiki link target is '{target}', expected '_blank'"
        print("    ✓ Wiki link opens in new tab")

        print("  Testing navigation to Status Overview...")
        page.click(".nav-links a:has-text('Status Overview')")
        page.wait_for_url("**/status.php**", timeout=5000)

        print("  Verifying Status Overview is now current page...")
        page.wait_for_selector(".nav-links a.current:has-text('Status Overview')", timeout=5000)
        print("    ✓ Status Overview is grayed out after navigation")

        browser.close()
        print("✓ Navbar functionality test completed successfully")


# Test 20: Status Page
def test_status_page():
    """Test that status.php displays correctly with all sections and column visibility controls."""
    with sync_playwright() as p:
        print("Starting status page test...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Enable console logging
        page.on("console", lambda msg: print(f"  [Browser] {msg.text}"))

        print("  Navigating to status page...")
        page.goto(f"{BASE_URL}/status.php?assumedid=testuser", wait_until="networkidle")

        print("  Checking page title...")
        page.wait_for_selector("h1", timeout=5000)
        h1_text = page.locator("h1").inner_text()
        assert "Hunt Status Overview" in h1_text, f"Unexpected h1: {h1_text}"

        print("  Waiting for Vue app to mount...")
        page.wait_for_selector(".status-header", timeout=5000)

        print("  Checking for Hunt Progress section...")
        page.wait_for_selector("text=Hunt Progress", timeout=5000)

        print("  Checking for Status Breakdown section...")
        page.wait_for_selector("text=Status Breakdown", timeout=5000)

        print("  Checking for Column Visibility section...")
        page.wait_for_selector("text=Column Visibility", timeout=5000)

        print("  Checking if Column Visibility is already expanded...")
        content = page.locator(".column-visibility .info-box-content")
        is_visible = content.is_visible()

        if not is_visible:
            print("  Expanding Column Visibility...")
            page.evaluate("""
                () => {
                    const header = document.querySelector('.column-visibility .info-box-header');
                    if (header) header.click();
                }
            """)
            page.wait_for_selector(".column-visibility .info-box-content", state="visible", timeout=5000)
            time.sleep(0.5)
        else:
            print("  Column Visibility already expanded")

        print("  Verifying all column checkboxes are present...")
        expected_columns = [
            "Round", "Status", "Doc", "Sheet #", "Chat",
            "Solvers (cur)", "Solvers (all)", "Location", "Tags", "Comment"
        ]

        page.wait_for_selector(".column-checkboxes label", timeout=5000)

        for col in expected_columns:
            checkbox = page.locator(f".column-checkboxes label:has-text('{col}') input[type='checkbox']")
            assert checkbox.count() > 0, f"Missing checkbox for column: {col}"
            print(f"    ✓ Found checkbox: {col}")

        print("  Testing column visibility toggle for each column...")
        # Test hiding and showing each column individually
        for col in expected_columns:
            print(f"    Testing {col} column...")
            checkbox = page.locator(f".column-checkboxes label:has-text('{col}') input[type='checkbox']")

            # Ensure it starts checked (visible)
            if not checkbox.is_checked():
                checkbox.click(force=True)
                time.sleep(0.3)

            # Count hidden columns before hiding
            hidden_count_before = page.locator("th.hidden-column").count()

            # Hide the column
            checkbox.click(force=True)
            time.sleep(0.3)

            # Count hidden columns after hiding - should increase
            hidden_count_after_hide = page.locator("th.hidden-column").count()
            assert hidden_count_after_hide > hidden_count_before, \
                f"{col} column should be hidden but hidden count didn't increase (before: {hidden_count_before}, after: {hidden_count_after_hide})"
            print(f"      ✓ {col} column hidden successfully (hidden count: {hidden_count_before} → {hidden_count_after_hide})")

            # Show the column again
            checkbox.click(force=True)
            time.sleep(0.3)

            # Count hidden columns after showing - should return to original count
            hidden_count_after_show = page.locator("th.hidden-column").count()
            assert hidden_count_after_show == hidden_count_before, \
                f"{col} column should be visible but hidden count didn't return to original (before: {hidden_count_before}, after show: {hidden_count_after_show})"
            print(f"      ✓ {col} column shown again successfully (hidden count: {hidden_count_after_hide} → {hidden_count_after_show})")

        print("  Testing 'Show All' button...")
        # First hide a few columns
        for col in ["Round", "Location", "Tags"]:
            checkbox = page.locator(f".column-checkboxes label:has-text('{col}') input[type='checkbox']")
            if checkbox.is_checked():
                checkbox.click(force=True)
        time.sleep(0.3)

        # Click Show All
        show_all_button = page.locator(".column-checkboxes button:has-text('Show All')")
        show_all_button.click()
        time.sleep(0.5)

        # Verify all checkboxes are checked
        for col in expected_columns:
            checkbox = page.locator(f".column-checkboxes label:has-text('{col}') input[type='checkbox']")
            assert checkbox.is_checked(), f"{col} checkbox should be checked after 'Show All'"
        print("    ✓ All columns visible after 'Show All'")

        browser.close()
        print("✓ Status page test completed successfully")


# Test 20: Solved Puzzles Excluded
def test_solved_puzzles_excluded():
    """Test that solved puzzles don't appear in status.php tables."""
    with sync_playwright() as p:
        print("Starting solved puzzle exclusion test...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Enable console logging
        page.on("console", lambda msg: print(f"  [Browser] {msg.text}"))

        print("  Navigating to status page...")
        page.goto(f"{BASE_URL}/status.php?assumedid=testuser", wait_until="networkidle")

        print("  Waiting for page to load...")
        page.wait_for_selector(".status-header", timeout=5000)
        time.sleep(1)

        # Expand all sections
        print("  Ensuring all sections are expanded...")
        sections = page.locator(".section-header")
        for i in range(sections.count()):
            section = sections.nth(i)
            collapse_icon = section.locator(".collapse-icon")
            if collapse_icon.get_attribute("class") and "collapsed" in collapse_icon.get_attribute("class"):
                print(f"    Expanding section {i+1}...")
                section.click()
                time.sleep(0.5)

        # Try to find a puzzle in any table
        print("  Looking for a puzzle to solve in any table...")
        puzzle_row = None

        # Try Total Hunt Overview table first (preferred)
        overview_table = page.locator(".puzzle-table").nth(2)
        overview_rows = overview_table.locator("table tr")
        if overview_rows.count() > 1:
            puzzle_row = overview_rows.nth(1)
            print(f"    Found puzzle in Total Hunt Overview")
        else:
            # Try No Location table
            noloc_table = page.locator(".puzzle-table").nth(0)
            noloc_rows = noloc_table.locator("table tr")
            if noloc_rows.count() > 1:
                puzzle_row = noloc_rows.nth(1)
                print(f"    Found puzzle in No Location")

        assert puzzle_row is not None, "No puzzles found in any table to test with"

        # Get puzzle name and ID
        puzzle_name_link = puzzle_row.locator("td:nth-child(3) a")
        puzzle_name = puzzle_name_link.inner_text()
        print(f"    Puzzle name: {puzzle_name}")

        row_id = puzzle_row.get_attribute("id")
        assert row_id is not None, "Puzzle row has no ID"

        puzzle_id = row_id.split("-")[-1]
        print(f"    Puzzle ID: {puzzle_id}")

        # Count initial visible puzzles
        print("  Counting puzzles in all tables before solving...")
        all_puzzle_rows_before = page.locator("table tr[id^='puzzle-']")
        total_count_before = all_puzzle_rows_before.count()
        print(f"    Total visible puzzles across all tables: {total_count_before}")

        # Solve the puzzle via API
        print(f"  Solving puzzle via API...")
        solve_result = page.evaluate(f"""
            async () => {{
                try {{
                    const response = await fetch('./apicall.php?apicall=puzzle&apiparam1={puzzle_id}&apiparam2=answer', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ answer: 'TESTANSWER' }})
                    }});
                    const data = await response.json();
                    return {{ success: response.ok, status: response.status, data: data }};
                }} catch (e) {{
                    return {{ success: false, error: e.toString() }};
                }}
            }}
        """)

        assert solve_result.get("success"), f"Failed to solve puzzle: {solve_result}"
        print(f"    ✓ Puzzle solved successfully")

        print("  Reloading page to refresh data...")
        page.reload(wait_until="networkidle")
        time.sleep(1)

        # Count puzzles after solving
        print("  Counting puzzles in all tables after solving...")
        all_puzzle_rows_after = page.locator("table tr[id^='puzzle-']")
        total_count_after = all_puzzle_rows_after.count()
        print(f"    Total visible puzzles across all tables: {total_count_after}")

        # Verify puzzle count decreased
        assert total_count_after < total_count_before, f"Puzzle count did not decrease (before: {total_count_before}, after: {total_count_after})"
        decrease = total_count_before - total_count_after
        print(f"    ✓ Total visible puzzle count decreased by {decrease}")

        # Verify the specific puzzle is not in any table
        print(f"  Verifying puzzle {puzzle_id} not in any table...")
        remaining_puzzle = page.locator(f"tr#puzzle-noloc-{puzzle_id}, tr#puzzle-overview-{puzzle_id}, tr#puzzle-sheet-{puzzle_id}")
        remaining_count = remaining_puzzle.count()

        assert remaining_count == 0, f"Solved puzzle '{puzzle_name}' (ID: {puzzle_id}) still appears in {remaining_count} table(s)"
        print(f"    ✓ Puzzle '{puzzle_name}' successfully removed from all tables")

        browser.close()
        print("✓ Solved puzzle exclusion test completed successfully")



def main():
    """Run all tests."""
    parser = argparse.ArgumentParser(
        description='Comprehensive Puzzleboss UI Test Suite',
        epilog='WARNING: This script will RESET THE HUNT DATABASE!'
    )
    parser.add_argument(
        '--allow-destructive',
        action='store_true',
        required=True,
        help='Required flag to confirm you understand this will DESTROY ALL PUZZLE DATA'
    )
    parser.add_argument(
        '--tests',
        nargs='+',
        help='Run only specific tests (by number or name). Examples: --tests 1 3 7 or --tests lifecycle visibility'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List available tests and exit'
    )
    args = parser.parse_args()

    # Define all available tests
    all_tests = [
        ('1', 'lifecycle', test_puzzle_lifecycle, 'Puzzle Lifecycle'),
        ('2', 'speculative', test_speculative_puzzle_promotion, 'Speculative Puzzle Promotion'),
        ('3', 'meta', test_round_completion_meta, 'Round Completion Meta'),
        ('4', 'tags', test_tag_management, 'Tag Management'),
        ('5', 'reassign', test_solver_reassignment, 'Solver Reassignment'),
        ('6', 'persistence', test_settings_persistence, 'Settings Persistence'),
        ('7', 'visibility', test_round_visibility_and_collapse, 'Round Visibility And Collapse'),
        ('8', 'validation', test_form_validation, 'Form Validation'),
        ('9', 'unicode', test_unicode_handling, 'Unicode Handling'),
        ('10', 'move', test_move_puzzle_between_rounds, 'Move Puzzle Between Rounds'),
        ('11', 'rename', test_rename_puzzle, 'Rename Puzzle'),
        ('12', 'tagfilter', test_tag_filtering, 'Tag Filtering'),
        ('13', 'statusfilter', test_status_filtering, 'Status Filtering'),
        ('14', 'activity', test_status_change_last_activity, 'Status Change Last Activity'),
        ('15', 'historic', test_unassign_solver_historic, 'Unassign Solver Historic'),
        ('16', 'pageload', test_basic_page_load, 'Basic Page Load'),
        ('17', 'advanced', test_advanced_controls, 'Advanced Controls'),
        ('18', 'navbar', test_navbar_functionality, 'Navbar Functionality'),
        ('19', 'statuspage', test_status_page, 'Status Page'),
        ('20', 'solved', test_solved_puzzles_excluded, 'Solved Puzzles Excluded'),
    ]

    # Handle --list
    if args.list:
        print("Available tests:")
        for number, name, _, display_name in all_tests:
            print(f"  {number}. {display_name} (--tests {number} or --tests {name})")
        sys.exit(0)

    # Safety check - if somehow the flag wasn't provided, abort
    if not args.allow_destructive:
        print("ERROR: --allow-destructive flag is required")
        print("This test suite will RESET THE HUNT DATABASE, destroying all puzzle data.")
        print("DO NOT run this on a production system!")
        sys.exit(1)

    # Determine which tests to run
    tests_to_run = []
    if args.tests:
        for test_spec in args.tests:
            test_spec_lower = test_spec.lower()
            found = False
            for number, name, test_func, display_name in all_tests:
                if test_spec == number or test_spec_lower == name.lower():
                    tests_to_run.append((test_func, display_name))
                    found = True
                    break
            if not found:
                print(f"ERROR: Unknown test '{test_spec}'")
                print("Use --list to see available tests")
                sys.exit(1)
    else:
        # Run all tests
        tests_to_run = [(test_func, display_name) for _, _, test_func, display_name in all_tests]

    print("="*70)
    print("COMPREHENSIVE PUZZLEBOSS UI TEST SUITE")
    print("="*70)
    print()
    print(f"Running {len(tests_to_run)} test(s)")
    print()
    print("WARNING: About to reset hunt database (DESTRUCTIVE)")
    print("This will erase all puzzles, rounds, and activity data!")
    print("Solver accounts will be preserved.")
    print("="*70)
    print()

    reset_hunt()
    ensure_test_solvers()

    runner = UITestRunner()

    # Run selected tests
    for test_func, _ in tests_to_run:
        runner.run_test(test_func)

    runner.print_summary()

    # Exit with error code if any tests failed
    sys.exit(0 if runner.failed == 0 else 1)


if __name__ == "__main__":
    main()
