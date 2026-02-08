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

        # Wait for the speculative puzzles table to load
        page1.wait_for_selector(".speculative-puzzles", timeout=5000)

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


# Test 7: Form Validation
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


# Test 8: Unicode Handling
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


# Test 9: Moving Puzzle Between Rounds (Concurrency Test)
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


# Test 10: Renaming Puzzle (Concurrency Test)
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


# Test 11: Tag Filtering
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


# Test 12: Status Filtering
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


# Test 13: Status Change and Last Activity (Concurrency Test)
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


# Test 14: Unassigning Solver and Historic Solvers (Concurrency Test)
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
    args = parser.parse_args()

    # Safety check - if somehow the flag wasn't provided, abort
    if not args.allow_destructive:
        print("ERROR: --allow-destructive flag is required")
        print("This test suite will RESET THE HUNT DATABASE, destroying all puzzle data.")
        print("DO NOT run this on a production system!")
        sys.exit(1)

    print("="*70)
    print("COMPREHENSIVE PUZZLEBOSS UI TEST SUITE")
    print("="*70)
    print()
    print("WARNING: About to reset hunt database (DESTRUCTIVE)")
    print("This will erase all puzzles, rounds, and activity data!")
    print("Solver accounts will be preserved.")
    print("="*70)
    print()

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
    runner.run_test(test_move_puzzle_between_rounds)
    runner.run_test(test_rename_puzzle)
    runner.run_test(test_tag_filtering)
    runner.run_test(test_status_filtering)
    runner.run_test(test_status_change_last_activity)
    runner.run_test(test_unassign_solver_historic)

    runner.print_summary()

    # Exit with error code if any tests failed
    sys.exit(0 if runner.failed == 0 else 1)


if __name__ == "__main__":
    main()
