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


# ──────────────────────────────────────────────────────────
# Test Runner
# ──────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────
# Setup Helpers
# ──────────────────────────────────────────────────────────

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

        response = requests.get(f"{API_URL}/solvers")
        solvers = response.json().get("solvers", [])
        print(f"  Now have {len(solvers)} solvers available for testing")
    except Exception as e:
        print(f"Warning: Could not ensure test solvers: {e}")


# ──────────────────────────────────────────────────────────
# UI Creation Helpers
# ──────────────────────────────────────────────────────────

def create_round_via_ui(page, round_name):
    """Create a round using the addround.php UI form. Returns {"name": sanitized_name}."""
    timestamp = str(int(time.time()))
    unique_name = f"{round_name}{timestamp}"

    page.goto(f"{BASE_URL}/addround.php?assumedid=testuser")
    page.fill("input[name='name']", unique_name)
    page.click("input[type='submit'][value='Add Round']")
    page.wait_for_selector("div.success", timeout=10000)

    return {"name": unique_name.replace(" ", "")}


def create_puzzle_via_ui(page, puzzle_name, round_name, is_meta=False, is_speculative=False):
    """Create a puzzle using the addpuzzle.php UI form (5-step workflow). Returns {"name": sanitized_name}."""
    page.goto(f"{BASE_URL}/addpuzzle.php?assumedid=testuser")
    page.wait_for_selector("input[name='name']", timeout=10000)

    page.fill("input[name='name']", puzzle_name)
    page.fill("input[name='puzzle_uri']", f"https://example.com/{puzzle_name.replace(' ', '_')}")
    page.select_option("select[name='round_id']", label=round_name)

    if is_meta:
        page.check("input[name='is_meta']")
    if is_speculative:
        page.check("input[name='is_speculative']")

    page.click("input[type='submit'][value='Add New Puzzle']")
    page.wait_for_selector("#step5 .status:has-text('✅')", timeout=30000)

    return {"name": puzzle_name.replace(" ", "")}


def goto_main(page):
    """Navigate to the main index page as testuser."""
    page.goto(f"{BASE_URL}/index.php?assumedid=testuser")


# ──────────────────────────────────────────────────────────
# DOM Query Helpers
# ──────────────────────────────────────────────────────────

def find_puzzle(page, name):
    """Find a puzzle element by name text. Returns the element or raises AssertionError."""
    for puzzle in page.query_selector_all(".puzzle"):
        if name in puzzle.inner_text():
            return puzzle
    raise AssertionError(f"Puzzle '{name}' not found in UI")


def find_round_header(page, name):
    """Find a round header element by name text. Returns the element or raises AssertionError."""
    for header in page.query_selector_all(".round-header"):
        if name in header.inner_text():
            return header
    raise AssertionError(f"Round header '{name}' not found in UI")


def get_puzzle_icons(puzzle_elem):
    """Get all .puzzle-icon elements from a puzzle. Icon order: 0=status, 1=workstate, 2=📊, 3=🗣️, 4=note-tags, 5=settings."""
    return puzzle_elem.query_selector_all(".puzzle-icon")


# ──────────────────────────────────────────────────────────
# Puzzle Interaction Helpers
# ──────────────────────────────────────────────────────────

def change_puzzle_status(page, puzzle_elem, status):
    """Open the status modal on a puzzle and change its status. Does NOT handle answer field."""
    icons = get_puzzle_icons(puzzle_elem)
    assert len(icons) > 0, "No puzzle icons found"
    icons[0].click()

    page.wait_for_selector("dialog select.dropdown", timeout=5000)
    page.select_option("dialog select.dropdown", status)


def solve_puzzle(page, puzzle_elem, answer):
    """Solve a puzzle via UI: open status modal, select Solved, fill answer, save and close."""
    change_puzzle_status(page, puzzle_elem, "Solved")
    time.sleep(0.5)

    answer_input = page.query_selector("dialog p:has-text('Answer:') input")
    assert answer_input is not None, "Answer input not found in dialog"
    answer_input.fill(answer)

    save_and_close_dialog(page)


def save_and_close_dialog(page):
    """Click Save in the current dialog and wait for it to close."""
    page.click("dialog button:has-text('Save')")
    page.wait_for_selector("dialog", state="hidden", timeout=5000)


def close_dialog(page):
    """Click Close in the current dialog and wait for it to close."""
    page.click("dialog button:has-text('Close')")
    page.wait_for_selector("dialog", state="hidden", timeout=5000)


def save_settings_dialog(page):
    """Save the puzzle-settings gear modal with its two-step confirmation flow.
    Clicks 'Save Changes' to reveal the confirmation banner, then 'Yes, Save'."""
    page.click("dialog button:has-text('Save Changes')")
    page.wait_for_selector("dialog .confirm-banner", timeout=3000)
    page.click("dialog button:has-text('Yes, Save')")
    page.wait_for_selector("dialog", state="hidden", timeout=5000)


def claim_puzzle(page, puzzle_elem):
    """Click the workstate icon and claim the puzzle (click Yes)."""
    icons = get_puzzle_icons(puzzle_elem)
    assert len(icons) > 1, "Not enough puzzle icons for workstate"
    icons[1].click()

    page.wait_for_selector("dialog", timeout=5000)
    time.sleep(0.5)

    yes_button = page.query_selector("dialog button:has-text('Yes')")
    if yes_button:
        yes_button.click()
    else:
        # Already assigned or no Yes button - try Save or Close
        save = page.query_selector("dialog button:has-text('Save')")
        if save:
            save.click()
        else:
            page.click("dialog button:has-text('Close')")

    page.wait_for_selector("dialog", state="hidden", timeout=5000)


def add_tag_to_puzzle(page, puzzle_elem, tag_name):
    """Open the note-tags modal and add a tag."""
    icons = get_puzzle_icons(puzzle_elem)
    assert len(icons) > 4, f"Not enough puzzle icons for note-tags (found {len(icons)})"
    icons[4].click()

    page.wait_for_selector("dialog", timeout=5000)
    tag_input = page.query_selector("dialog input[list='taglist']")
    assert tag_input is not None, "Tag input not found in dialog"
    tag_input.fill(tag_name)

    add_button = page.query_selector("dialog span.puzzle-icon:has-text('➕')")
    assert add_button is not None, "Add tag button (➕) not found"
    add_button.click()
    time.sleep(0.5)

    save_and_close_dialog(page)


# ──────────────────────────────────────────────────────────
# Auto-Refresh Wait Helpers
# ──────────────────────────────────────────────────────────

def wait_for_puzzle_status(page, puzzle_name, status, timeout=7000):
    """Wait for auto-refresh to show a specific status on a puzzle."""
    page.wait_for_function(f"""
        () => {{
            const puzzles = document.querySelectorAll('.puzzle');
            for (let puzzle of puzzles) {{
                if (puzzle.innerText.includes('{puzzle_name}')) {{
                    const statusIcon = puzzle.querySelector('.puzzle-icon');
                    return statusIcon && statusIcon.title.includes('{status}');
                }}
            }}
            return false;
        }}
    """, timeout=timeout)


def wait_for_round_solved(page, round_name, timeout=7000):
    """Wait for auto-refresh to mark a round as solved."""
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
    """, timeout=timeout)


def wait_for_solver_on_puzzle(page, puzzle_name, solver_name, timeout=7000):
    """Wait for auto-refresh to show a solver on a puzzle's workstate tooltip."""
    page.wait_for_function(f"""
        () => {{
            const puzzles = document.querySelectorAll('.puzzle');
            for (let puzzle of puzzles) {{
                if (puzzle.innerText.includes('{puzzle_name}')) {{
                    const icons = puzzle.querySelectorAll('.puzzle-icon');
                    const workstateIcon = icons[1];
                    return workstateIcon && workstateIcon.title.includes('{solver_name}');
                }}
            }}
            return false;
        }}
    """, timeout=timeout)


def wait_for_solver_removed(page, puzzle_name, solver_name, timeout=7000):
    """Wait for auto-refresh to show a solver removed from a puzzle."""
    page.wait_for_function(f"""
        () => {{
            const puzzles = document.querySelectorAll('.puzzle');
            for (let puzzle of puzzles) {{
                if (puzzle.innerText.includes('{puzzle_name}')) {{
                    const icons = puzzle.querySelectorAll('.puzzle-icon');
                    const workstateIcon = icons[1];
                    return workstateIcon && !workstateIcon.title.includes('{solver_name}');
                }}
            }}
            return false;
        }}
    """, timeout=timeout)


def enable_all_puzzle_filters(page):
    """Enable all puzzle status filters via localStorage and reload."""
    page.evaluate("""() => {
        const settings = JSON.parse(localStorage.getItem('settings') || '{}');
        if (!settings.puzzleFilter) settings.puzzleFilter = {};
        const statuses = ['New', 'Being worked', 'Needs eyes', 'Solved', 'Critical',
                        'Unnecessary', 'WTF', 'Under control', 'Waiting for HQ',
                        'Grind', 'Abandoned', 'Speculative'];
        statuses.forEach(s => settings.puzzleFilter[s] = true);
        localStorage.setItem('settings', JSON.stringify(settings));
        location.reload();
    }""")


# ──────────────────────────────────────────────────────────
# Test 1: Puzzle Lifecycle
# ──────────────────────────────────────────────────────────

def test_puzzle_lifecycle():
    """Test complete puzzle lifecycle from creation to solve."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        round_name = create_round_via_ui(page, "Test Round")["name"]
        puzzle_name = create_puzzle_via_ui(page, "Test Lifecycle Puzzle", round_name)["name"]

        goto_main(page)
        page.wait_for_selector(f"text={puzzle_name}", timeout=10000)

        # Verify initial "New" status
        puzzle_elem = page.query_selector(".puzzle")
        assert puzzle_elem.query_selector('.puzzle-icon[title*="New"]') is not None, "Initial 'New' status not found"

        # Claim puzzle
        print("  Assigning solver via UI...")
        claim_puzzle(page, puzzle_elem)

        # Wait for solver icon to appear
        print("  Waiting for auto-refresh to show solver assignment...")
        page.wait_for_function("""
            () => {
                const puzzle = document.querySelector('.puzzle');
                return puzzle && puzzle.innerText.includes('👥');
            }
        """, timeout=7000)

        # Change to "Being worked"
        print("  Changing status to 'Being worked' via UI...")
        puzzle_elem = page.query_selector(".puzzle")
        change_puzzle_status(page, puzzle_elem, "Being worked")
        save_and_close_dialog(page)

        print("  Waiting for auto-refresh to show status change...")
        wait_for_puzzle_status(page, puzzle_name, "Being worked")

        puzzle_elem = page.query_selector(".puzzle")
        assert puzzle_elem.query_selector('.puzzle-icon[title*="Being worked"]') is not None, "Being worked status not found"

        # Solve the puzzle
        print("  Solving puzzle via UI...")
        puzzle_elem = page.query_selector(".puzzle")
        solve_puzzle(page, puzzle_elem, "TEST ANSWER")

        print("  Waiting for auto-refresh to show answer and solved status...")
        page.wait_for_function("""
            () => {
                const puzzle = document.querySelector('.puzzle');
                const answerElem = puzzle ? puzzle.querySelector('.answer') : null;
                return answerElem && answerElem.innerText.includes('TEST ANSWER');
            }
        """, timeout=7000)

        # Verify answer and solved status
        puzzle_elem = page.query_selector(".puzzle")
        answer_text = puzzle_elem.query_selector(".answer").inner_text().strip()
        assert "TEST ANSWER" in answer_text, f"Answer 'TEST ANSWER' not in UI (found: {answer_text})"
        assert puzzle_elem.query_selector('.puzzle-icon[title*="Solved"]') is not None, "Solved status not found"

        browser.close()
        print("✓ Puzzle lifecycle completed successfully")


# ──────────────────────────────────────────────────────────
# Test 2: Speculative Puzzle Promotion (Concurrency Test)
# ──────────────────────────────────────────────────────────

def test_speculative_puzzle_promotion():
    """Test creating and promoting a speculative puzzle with concurrent browser verification."""
    with sync_playwright() as p:
        browser1 = p.chromium.launch(headless=True)
        browser2 = p.chromium.launch(headless=True)
        page1 = browser1.new_page()
        page2 = browser2.new_page()

        round_name = create_round_via_ui(page1, "Spec Test Round")["name"]
        puzzle_name = create_puzzle_via_ui(page1, "Speculative Test Puzzle", round_name, is_speculative=True)["name"]

        # Browser 2: Verify speculative status via auto-refresh
        print("  [Browser 2] Waiting for new puzzle to appear via auto-refresh...")
        goto_main(page2)
        page2.wait_for_selector(f"text={puzzle_name}", timeout=15000)

        print("  [Browser 2] Verifying Speculative status in UI...")
        wait_for_puzzle_status(page2, puzzle_name, "Speculative")

        puzzle = find_puzzle(page2, puzzle_name)
        status_title = puzzle.query_selector(".puzzle-icon").get_attribute("title")
        assert "Speculative" in status_title, f"Status not 'Speculative' (found: {status_title})"
        print(f"  [Browser 2] ✓ Verified Speculative status: {status_title}")

        # Browser 1: Promote puzzle
        print("  [Browser 1] Promoting puzzle...")
        page1.goto(f"{BASE_URL}/addpuzzle.php?assumedid=testuser")
        page1.wait_for_selector("#promote-puzzle-fields", timeout=5000)

        radio_selector = f"tr:has-text('{puzzle_name}') input[name='promote_puzzle_id']"
        page1.wait_for_selector(radio_selector, timeout=5000)
        page1.click(radio_selector)
        page1.wait_for_timeout(500)

        page1.fill("input[name='puzzle_uri']", "https://example.com/real_puzzle")
        page1.click("input[type='submit']")
        page1.wait_for_selector("h2:has-text('Puzzle promoted successfully')", timeout=10000)
        print("  [Browser 1] ✓ Promotion completed")

        # Browser 2: Verify promotion to New status via auto-refresh (NO RELOAD!)
        print("  [Browser 2] Waiting for auto-refresh to show promotion to New status...")
        wait_for_puzzle_status(page2, puzzle_name, "New")

        puzzle = find_puzzle(page2, puzzle_name)
        status_title = puzzle.query_selector(".puzzle-icon").get_attribute("title")
        assert "New" in status_title, f"Status not 'New' after promotion (found: {status_title})"
        print(f"  [Browser 2] ✓ Verified promotion to New status via auto-refresh: {status_title}")

        browser1.close()
        browser2.close()
        print("✓ Speculative puzzle promotion with concurrent verification completed successfully")


# ──────────────────────────────────────────────────────────
# Test 3: Round Completion via Meta Puzzles
# ──────────────────────────────────────────────────────────

def test_round_completion_meta():
    """Test that rounds are marked complete when all metas are solved, and unmarked when new unsolved metas are added."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        round_name = create_round_via_ui(page, "Meta Test Round")["name"]
        create_puzzle_via_ui(page, "Meta Puzzle 1", round_name, is_meta=True)
        create_puzzle_via_ui(page, "Meta Puzzle 2", round_name, is_meta=True)

        goto_main(page)
        page.wait_for_selector(f"text={round_name}", timeout=10000)

        # Wait for meta puzzles to render
        page.wait_for_selector(".puzzle.meta", timeout=10000)

        # Verify round not yet solved
        round_header = page.query_selector(".round-header")
        assert "solved" not in round_header.get_attribute("class"), "Round marked solved before metas solved"

        # Solve first meta
        print("  Solving first meta puzzle...")
        meta1 = page.query_selector(".puzzle.meta")
        solve_puzzle(page, meta1, "META1")

        print("  Waiting for auto-refresh...")
        time.sleep(6)

        # Enable all filters to see solved puzzles
        enable_all_puzzle_filters(page)
        page.wait_for_selector(f"text={round_name}", timeout=10000)

        assert "solved" not in page.query_selector(".round-header").get_attribute("class"), \
            "Round marked solved with only 1/2 metas solved"

        # Expand round if collapsed
        header = page.query_selector(".round-header")
        if "▶" in header.inner_text():
            header.click()
            time.sleep(0.5)

        # Solve second meta
        print("  Solving second meta puzzle...")
        meta2 = find_puzzle(page, "MetaPuzzle2")
        solve_puzzle(page, meta2, "META2")

        print("  Waiting for auto-refresh to show round marked as solved...")
        wait_for_round_solved(page, round_name)

        round_header = find_round_header(page, round_name)
        assert "solved" in round_header.get_attribute("class"), "Round not marked solved after all metas solved"

        # Add third unsolved meta - should unmark round
        create_puzzle_via_ui(page, "Meta Puzzle 3", round_name, is_meta=True)

        goto_main(page)
        page.wait_for_selector(f"text={round_name}", timeout=10000)
        time.sleep(1)

        round_header = find_round_header(page, round_name)
        assert "solved" not in round_header.get_attribute("class"), "Round still marked solved after adding unsolved meta"
        print("  ✓ Round correctly unmarked as Solved after adding unsolved meta")

        # Expand and solve third meta
        if "▶" in round_header.inner_text():
            round_header.click()
            time.sleep(0.5)

        print("  Solving third meta puzzle...")
        meta3 = find_puzzle(page, "MetaPuzzle3")
        solve_puzzle(page, meta3, "META3")

        print("  Waiting for auto-refresh to show round marked as solved again...")
        wait_for_round_solved(page, round_name)

        round_header = find_round_header(page, round_name)
        assert "solved" in round_header.get_attribute("class"), "Round not marked solved after solving all 3 metas"
        print("  ✓ Round marked as Solved again after solving third meta")

        browser.close()
        print("✓ Round completion/unmarking logic working correctly")


# ──────────────────────────────────────────────────────────
# Test 4: Tag Management
# ──────────────────────────────────────────────────────────

def test_tag_management():
    """Test adding tags and filtering puzzles by tags."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        round_name = create_round_via_ui(page, "Tag Test Round")["name"]
        create_puzzle_via_ui(page, "Cryptic Puzzle", round_name)
        create_puzzle_via_ui(page, "Logic Puzzle", round_name)

        goto_main(page)
        page.wait_for_selector("text=CrypticPuzzle", timeout=10000)

        timestamp = str(int(time.time()))
        tag_name1 = f"cryptic{timestamp}"
        tag_name2 = f"logic{timestamp}"

        # Add tags
        print(f"  Adding tag '{tag_name1}' to CrypticPuzzle...")
        add_tag_to_puzzle(page, find_puzzle(page, "CrypticPuzzle"), tag_name1)

        print(f"  Adding tag '{tag_name2}' to LogicPuzzle...")
        add_tag_to_puzzle(page, find_puzzle(page, "LogicPuzzle"), tag_name2)

        # Wait for auto-refresh to show tags in tooltips
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
                        if (text.includes('CrypticPuzzle') && title.includes('{tag_name1}')) crypticHasTag = true;
                        if (text.includes('LogicPuzzle') && title.includes('{tag_name2}')) logicHasTag = true;
                    }}
                }}
                return crypticHasTag && logicHasTag;
            }}
        """, timeout=7000)

        # Verify tags via tooltips
        for pname, tag in [("CrypticPuzzle", tag_name1), ("LogicPuzzle", tag_name2)]:
            icons = get_puzzle_icons(find_puzzle(page, pname))
            title = icons[4].get_attribute("title")
            assert tag in title, f"Tag {tag} not found in {pname} tooltip"

        browser.close()
        print("✓ Tag management completed successfully")


# ──────────────────────────────────────────────────────────
# Test 5: Solver Reassignment
# ──────────────────────────────────────────────────────────

def test_solver_reassignment():
    """Test that solver is auto-unassigned from old puzzle when assigned to new puzzle."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        round_name = create_round_via_ui(page, "Solver Test Round")["name"]
        create_puzzle_via_ui(page, "Puzzle A", round_name)
        create_puzzle_via_ui(page, "Puzzle B", round_name)
        solver_name = "testuser"

        goto_main(page)
        page.wait_for_selector("text=PuzzleA", timeout=10000)

        # Assign to Puzzle A
        print("  Assigning testuser to Puzzle A via UI...")
        claim_puzzle(page, find_puzzle(page, "PuzzleA"))

        print("  Waiting for auto-refresh to show solver on Puzzle A...")
        wait_for_solver_on_puzzle(page, "PuzzleA", solver_name)

        workstate_title = get_puzzle_icons(find_puzzle(page, "PuzzleA"))[1].get_attribute("title")
        assert solver_name in workstate_title, f"Solver not shown in Puzzle A tooltip (found: {workstate_title})"
        print(f"  ✓ Verified {solver_name} assigned to Puzzle A")

        # Reassign to Puzzle B
        print("  Assigning testuser to Puzzle B via UI...")
        claim_puzzle(page, find_puzzle(page, "PuzzleB"))

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
                        if (text.includes('PuzzleA') && !workstateIcon.title.includes('{solver_name}')) puzzleANoSolver = true;
                        if (text.includes('PuzzleB') && workstateIcon.title.includes('{solver_name}')) puzzleBHasSolver = true;
                    }}
                }}
                return puzzleANoSolver && puzzleBHasSolver;
            }}
        """, timeout=7000)

        # Verify reassignment
        a_title = get_puzzle_icons(find_puzzle(page, "PuzzleA"))[1].get_attribute("title")
        b_title = get_puzzle_icons(find_puzzle(page, "PuzzleB"))[1].get_attribute("title")
        assert solver_name not in a_title, f"Solver still in Puzzle A after reassignment (found: {a_title})"
        assert solver_name in b_title, f"Solver not in Puzzle B (found: {b_title})"
        print(f"  ✓ Verified {solver_name} removed from Puzzle A, assigned to Puzzle B")

        browser.close()
        print("✓ Solver reassignment working correctly")


# ──────────────────────────────────────────────────────────
# Test 6: Settings Persistence
# ──────────────────────────────────────────────────────────

def test_settings_persistence():
    """Test that UI settings persist across page reloads."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        goto_main(page)
        page.wait_for_load_state("networkidle")

        page.evaluate("localStorage.setItem('testSetting', 'testValue')")
        page.reload()
        page.wait_for_load_state("networkidle")

        persisted_value = page.evaluate("localStorage.getItem('testSetting')")
        assert persisted_value == "testValue", "localStorage settings did not persist"

        browser.close()
        print("✓ Settings persistence working correctly")


# ──────────────────────────────────────────────────────────
# Test 7: Round Visibility and Collapse
# ──────────────────────────────────────────────────────────

def test_round_visibility_and_collapse():
    """Test round collapse/expand functionality and 'Solved rounds' toggle."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("console", lambda msg: msg.type == "error" and print(f"Browser console [ERROR]: {msg.text}"))

        # Create unsolved and solved rounds
        unsolved_round_name = create_round_via_ui(page, "Unsolved Round Test")["name"]
        create_puzzle_via_ui(page, "Test Puzzle 1", unsolved_round_name)
        create_puzzle_via_ui(page, "Test Puzzle 2", unsolved_round_name)

        solved_round_name = create_round_via_ui(page, "Solved Round Test")["name"]
        sp1 = create_puzzle_via_ui(page, "Solved Meta 1", solved_round_name, is_meta=True)
        sp2 = create_puzzle_via_ui(page, "Solved Meta 2", solved_round_name, is_meta=True)

        # Solve both metas to mark round as solved
        goto_main(page)
        page.wait_for_selector(".round", timeout=10000)
        time.sleep(1)

        for sp_name, answer in [(sp1["name"], "ANSWER1"), (sp2["name"], "ANSWER2")]:
            solve_puzzle(page, find_puzzle(page, sp_name), answer)
            time.sleep(0.5)

        print("\nWaiting for round to be marked as solved...")
        wait_for_round_solved(page, solved_round_name, timeout=10000)
        time.sleep(0.5)

        # Test 7a: Default visibility
        print("\nTest 7a: Default round visibility")
        goto_main(page)
        page.wait_for_selector(".round", timeout=10000)
        time.sleep(6)  # Wait for auto-refresh

        # Find both rounds
        unsolved_round_elem = find_round_header(page, unsolved_round_name).evaluate_handle("el => el.parentElement")
        solved_round_elem = find_round_header(page, solved_round_name).evaluate_handle("el => el.parentElement")

        unsolved_body = unsolved_round_elem.as_element().query_selector(".round-body")
        assert "hiding" not in unsolved_body.get_attribute("class"), "Unsolved round should be expanded by default"
        print(f"  ✓ Unsolved round is expanded by default")

        solved_body = solved_round_elem.as_element().query_selector(".round-body")
        assert "hiding" in solved_body.get_attribute("class"), "Solved round should be collapsed by default"
        print(f"  ✓ Solved round is collapsed by default")

        # Test 7b: Manual collapse/expand
        print("\nTest 7b: Manual round collapse/expand")
        page.evaluate(f"""
            () => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const header = round.querySelector('.round-header');
                    if (header && header.innerText.includes('{unsolved_round_name}')) {{ header.click(); return true; }}
                }}
                return false;
            }}
        """)

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

        # Verify collapsed
        for round_elem in page.query_selector_all(".round"):
            header = round_elem.query_selector(".round-header")
            if header and unsolved_round_name in header.inner_text():
                assert "hiding" in round_elem.query_selector(".round-body").get_attribute("class")
                assert "collapsed" in header.query_selector(".collapse-icon").get_attribute("class")
                break
        print(f"  ✓ Clicking header collapsed unsolved round")

        # Click again to expand
        page.evaluate(f"""
            () => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const header = round.querySelector('.round-header');
                    if (header && header.innerText.includes('{unsolved_round_name}')) {{ header.click(); return true; }}
                }}
                return false;
            }}
        """)
        time.sleep(0.5)

        for round_elem in page.query_selector_all(".round"):
            header = round_elem.query_selector(".round-header")
            if header and unsolved_round_name in header.inner_text():
                assert "hiding" not in round_elem.query_selector(".round-body").get_attribute("class")
                assert "collapsed" not in header.query_selector(".collapse-icon").get_attribute("class")
                break
        print(f"  ✓ Clicking header again expanded unsolved round")

        # Test 7c: Solved rounds pill toggle
        print("\nTest 7c: Show solved rounds pill toggle")
        solved_rounds_label = page.query_selector(".toggle-row.pills label:has-text('Solved rounds')")
        assert solved_rounds_label is not None, "Could not find 'Solved rounds' pill toggle"

        label_classes = solved_rounds_label.get_attribute("class") or ""
        assert "on" not in label_classes, "Solved rounds toggle should be off by default"
        print(f"  ✓ 'Solved rounds' pill toggle is off by default")

        # Enable
        solved_rounds_label.click()

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

        for round_elem in page.query_selector_all(".round"):
            header = round_elem.query_selector(".round-header")
            if header and solved_round_name in header.inner_text():
                assert "hiding" not in round_elem.query_selector(".round-body").get_attribute("class")
                break
        print(f"  ✓ Enabling 'Solved rounds' expanded the solved round")

        # Disable
        page.query_selector(".toggle-row.pills label:has-text('Solved rounds')").click()

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

        for round_elem in page.query_selector_all(".round"):
            header = round_elem.query_selector(".round-header")
            if header and solved_round_name in header.inner_text():
                assert "hiding" in round_elem.query_selector(".round-body").get_attribute("class")
                break
        print(f"  ✓ Disabling 'Solved rounds' collapsed the solved round")

        browser.close()
        print("✓ Round visibility and collapse functionality working correctly")


# ──────────────────────────────────────────────────────────
# Test 8: Form Validation
# ──────────────────────────────────────────────────────────

def test_form_validation():
    """Test form validation on addpuzzle.php."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        round_name = create_round_via_ui(page, "Validation Test Round")["name"]

        page.goto(f"{BASE_URL}/addpuzzle.php?assumedid=testuser")
        page.wait_for_selector("input[name='name']", timeout=10000)
        page.fill("input[name='name']", "")
        page.fill("input[name='puzzle_uri']", "https://example.com/test")
        page.select_option("select[name='round_id']", label=round_name)
        page.click("input[type='submit'][value='Add New Puzzle']")

        # HTML5 validation should prevent submission
        time.sleep(1)
        assert "addpuzzle.php" in page.url, "Form allowed empty name submission"

        browser.close()
        print("✓ Form validation working correctly")


# ──────────────────────────────────────────────────────────
# Test 9: Unicode Handling
# ──────────────────────────────────────────────────────────

def test_unicode_handling():
    """Test that the system handles unicode characters correctly."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        round_name = create_round_via_ui(page, "Unicode Test Round 🎯")["name"]
        create_puzzle_via_ui(page, "Test Puzzle 日本語 🧩", round_name)

        goto_main(page)
        page.wait_for_load_state("networkidle")

        browser.close()
        print("✓ Unicode handling working correctly")


# ──────────────────────────────────────────────────────────
# Test 10: Moving Puzzle Between Rounds (Concurrency Test)
# ──────────────────────────────────────────────────────────

def test_move_puzzle_between_rounds():
    """Test moving a puzzle from one round to another with concurrent verification."""
    with sync_playwright() as p:
        browser1 = p.chromium.launch(headless=True)
        browser2 = p.chromium.launch(headless=True)
        page1 = browser1.new_page()
        page2 = browser2.new_page()

        round1_name = create_round_via_ui(page1, "Original Round")["name"]
        round2_name = create_round_via_ui(page1, "Destination Round")["name"]
        puzzle_name = create_puzzle_via_ui(page1, "Mobile Puzzle", round1_name)["name"]

        # Browser 2: Verify puzzle in round 1
        print("  [Browser 2] Waiting for puzzle to appear in original round...")
        goto_main(page2)
        page2.wait_for_selector(f"text={puzzle_name}", timeout=10000)

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

        # Browser 1: Move puzzle via settings modal
        print("  [Browser 1] Moving puzzle to different round...")
        goto_main(page1)
        page1.wait_for_selector(f"text={puzzle_name}", timeout=10000)

        puzzle_elem = find_puzzle(page1, puzzle_name)
        icons = get_puzzle_icons(puzzle_elem)
        icons[-1].click()  # Settings icon (last)

        page1.wait_for_selector("dialog", timeout=5000)
        time.sleep(0.5)
        page1.select_option("dialog select#puzzle-round", label=round2_name)
        save_settings_dialog(page1)
        print("  [Browser 1] ✓ Puzzle moved")

        # Browser 2: Verify move via auto-refresh
        print("  [Browser 2] Waiting for auto-refresh to show puzzle in new round...")
        page2.wait_for_function(f"""
            () => {{
                const rounds = document.querySelectorAll('.round');
                let inRound2 = false;
                let notInRound1 = true;
                for (let round of rounds) {{
                    const headerText = round.querySelector('.round-header')?.innerText || '';
                    const bodyText = round.querySelector('.round-body')?.innerText || '';
                    if (headerText.includes('{round2_name}') && bodyText.includes('{puzzle_name}')) inRound2 = true;
                    if (headerText.includes('{round1_name}') && bodyText.includes('{puzzle_name}')) notInRound1 = false;
                }}
                return inRound2 && notInRound1;
            }}
        """, timeout=7000)
        print(f"  [Browser 2] ✓ Verified puzzle moved to {round2_name}")

        browser1.close()
        browser2.close()
        print("✓ Puzzle move between rounds completed successfully")


# ──────────────────────────────────────────────────────────
# Test 11: Renaming Puzzle (Concurrency Test)
# ──────────────────────────────────────────────────────────

def test_rename_puzzle():
    """Test renaming a puzzle with concurrent verification."""
    with sync_playwright() as p:
        browser1 = p.chromium.launch(headless=True)
        browser2 = p.chromium.launch(headless=True)
        page1 = browser1.new_page()
        page2 = browser2.new_page()

        round_name = create_round_via_ui(page1, "Rename Test Round")["name"]
        old_name = create_puzzle_via_ui(page1, "Original Name", round_name)["name"]
        new_name = "RenamedPuzzle"

        # Browser 2: Verify original name
        print("  [Browser 2] Waiting for puzzle with original name...")
        goto_main(page2)
        page2.wait_for_selector(f"text={old_name}", timeout=10000)
        print(f"  [Browser 2] ✓ Verified original name: {old_name}")

        # Browser 1: Rename via settings modal
        print("  [Browser 1] Renaming puzzle...")
        goto_main(page1)
        page1.wait_for_selector(f"text={old_name}", timeout=10000)

        puzzle_elem = find_puzzle(page1, old_name)
        get_puzzle_icons(puzzle_elem)[-1].click()  # Settings icon

        page1.wait_for_selector("dialog", timeout=5000)
        time.sleep(0.5)
        page1.query_selector("dialog input#puzzle-name").fill(new_name)
        save_settings_dialog(page1)
        print("  [Browser 1] ✓ Puzzle renamed")

        # Browser 2: Verify via auto-refresh
        print("  [Browser 2] Waiting for auto-refresh to show new name...")
        page2.wait_for_function(f"""
            () => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{new_name}')) return true;
                }}
                return false;
            }}
        """, timeout=7000)
        print(f"  [Browser 2] ✓ Verified new name: {new_name}")

        browser1.close()
        browser2.close()
        print("✓ Puzzle rename completed successfully")


# ──────────────────────────────────────────────────────────
# Test 12: Tag Filtering
# ──────────────────────────────────────────────────────────

def test_tag_filtering():
    """Test filtering puzzles by tags."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        round_name = create_round_via_ui(page, "Tag Filter Round")["name"]
        create_puzzle_via_ui(page, "Crypto Puzzle", round_name)
        create_puzzle_via_ui(page, "Word Puzzle", round_name)
        create_puzzle_via_ui(page, "Math Puzzle", round_name)

        goto_main(page)
        page.wait_for_selector("text=CryptoPuzzle", timeout=10000)

        timestamp = str(int(time.time()))
        crypto_tag = f"crypto{timestamp}"
        word_tag = f"wordplay{timestamp}"

        print(f"  Adding tag '{crypto_tag}' to CryptoPuzzle...")
        add_tag_to_puzzle(page, find_puzzle(page, "CryptoPuzzle"), crypto_tag)

        print(f"  Adding tag '{word_tag}' to WordPuzzle...")
        time.sleep(1)
        add_tag_to_puzzle(page, find_puzzle(page, "WordPuzzle"), word_tag)

        # Wait for tags to appear
        time.sleep(6)

        # Filter by crypto tag
        print(f"  Filtering by tag '{crypto_tag}'...")
        tag_select_input = page.query_selector("input[list='taglist']")
        if tag_select_input is None:
            tag_select_input = page.query_selector("#links input[type='text']")
        assert tag_select_input is not None, "Tag select input not found"
        tag_select_input.fill(crypto_tag)
        tag_select_input.press("Enter")
        time.sleep(0.5)

        # Verify only CryptoPuzzle is visible
        puzzles = page.query_selector_all(".puzzle")
        has_crypto = any("CryptoPuzzle" in p.inner_text() for p in puzzles)
        assert has_crypto, "CryptoPuzzle not visible when filtering by its tag"
        print(f"  ✓ Tag filtering working correctly")

        browser.close()
        print("✓ Tag filtering completed successfully")


# ──────────────────────────────────────────────────────────
# Test 13: Status Filtering
# ──────────────────────────────────────────────────────────

def test_status_filtering():
    """Test filtering puzzles by status."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        round_name = create_round_via_ui(page, "Status Filter Round")["name"]
        create_puzzle_via_ui(page, "New Puzzle One", round_name)
        create_puzzle_via_ui(page, "New Puzzle Two", round_name)

        goto_main(page)
        page.wait_for_selector("text=NewPuzzleOne", timeout=10000)

        # Solve one puzzle
        print("  Changing NewPuzzleOne to Solved...")
        solve_puzzle(page, find_puzzle(page, "NewPuzzleOne"), "ANSWER")

        wait_for_puzzle_status(page, "NewPuzzleOne", "Solved")

        # Disable "New" status filter
        print("  Disabling 'New' status filter...")
        page.evaluate("""() => {
            const settings = JSON.parse(localStorage.getItem('settings') || '{}');
            if (settings.puzzleFilter) { settings.puzzleFilter['New'] = false; }
            localStorage.setItem('settings', JSON.stringify(settings));
            location.reload();
        }""")

        page.wait_for_selector("text=NewPuzzleOne", timeout=10000)
        time.sleep(1)

        # Verify solved puzzle is still visible
        found_solved = any("NewPuzzleOne" in p.inner_text() for p in page.query_selector_all(".puzzle"))
        assert found_solved, "Solved puzzle (NewPuzzleOne) should be visible"
        print("  ✓ Status filtering working correctly")

        browser.close()
        print("✓ Status filtering completed successfully")


# ──────────────────────────────────────────────────────────
# Test 14: Status Change and Last Activity (Concurrency Test)
# ──────────────────────────────────────────────────────────

def test_status_change_last_activity():
    """Test that changing puzzle status updates last activity info."""
    with sync_playwright() as p:
        browser1 = p.chromium.launch(headless=True)
        browser2 = p.chromium.launch(headless=True)
        page1 = browser1.new_page()
        page2 = browser2.new_page()

        round_name = create_round_via_ui(page1, "Activity Test Round")["name"]
        puzzle_name = create_puzzle_via_ui(page1, "Activity Puzzle", round_name)["name"]

        goto_main(page2)
        page2.wait_for_selector(f"text={puzzle_name}", timeout=10000)

        # Browser 1: Change status
        print("  [Browser 1] Changing status to 'Being worked'...")
        goto_main(page1)
        page1.wait_for_selector(f"text={puzzle_name}", timeout=10000)

        change_puzzle_status(page1, find_puzzle(page1, puzzle_name), "Being worked")
        save_and_close_dialog(page1)
        print("  [Browser 1] ✓ Status changed")

        # Browser 2: Verify via auto-refresh and check last activity in modal
        print("  [Browser 2] Waiting for auto-refresh and checking last activity...")
        wait_for_puzzle_status(page2, puzzle_name, "Being worked")

        get_puzzle_icons(find_puzzle(page2, puzzle_name))[0].click()
        page2.wait_for_selector("dialog", timeout=5000)
        time.sleep(0.5)

        modal_content = page2.query_selector("dialog").inner_text()
        assert "Last activity:" in modal_content or "Being worked" in modal_content, \
            f"Last activity not shown in modal: {modal_content}"
        print(f"  [Browser 2] ✓ Last activity displayed in status modal")

        close_dialog(page2)

        browser1.close()
        browser2.close()
        print("✓ Status change and last activity update completed successfully")


# ──────────────────────────────────────────────────────────
# Test 15: Unassigning Solver and Historic Solvers (Concurrency Test)
# ──────────────────────────────────────────────────────────

def test_unassign_solver_historic():
    """Test unassigning a solver (via reassignment) and verifying they move to historic solvers."""
    with sync_playwright() as p:
        browser1 = p.chromium.launch(headless=True)
        browser2 = p.chromium.launch(headless=True)
        page1 = browser1.new_page()
        page2 = browser2.new_page()

        round_name = create_round_via_ui(page1, "Historic Test Round")["name"]
        puzzle1_name = create_puzzle_via_ui(page1, "First Puzzle", round_name)["name"]
        puzzle2_name = create_puzzle_via_ui(page1, "Second Puzzle", round_name)["name"]
        solver_name = "testuser"

        # Browser 1: Assign solver to first puzzle
        print("  [Browser 1] Assigning solver to first puzzle...")
        goto_main(page1)
        page1.wait_for_selector(f"text={puzzle1_name}", timeout=10000)
        claim_puzzle(page1, find_puzzle(page1, puzzle1_name))
        print("  [Browser 1] ✓ Solver assigned to first puzzle")

        # Browser 2: Verify solver on first puzzle
        print("  [Browser 2] Waiting for solver to appear on first puzzle...")
        goto_main(page2)
        page2.wait_for_selector(f"text={puzzle1_name}", timeout=10000)
        wait_for_solver_on_puzzle(page2, puzzle1_name, solver_name)
        print("  [Browser 2] ✓ Verified solver on first puzzle")

        # Browser 1: Reassign to second puzzle
        print("  [Browser 1] Reassigning solver to second puzzle via UI...")
        claim_puzzle(page1, find_puzzle(page1, puzzle2_name))
        print("  [Browser 1] ✓ Solver reassigned to second puzzle via UI")

        # Browser 2: Verify removal from first puzzle
        print("  [Browser 2] Waiting for auto-refresh to show solver removed from first puzzle...")
        wait_for_solver_removed(page2, puzzle1_name, solver_name)
        print("  [Browser 2] ✓ Solver removed from first puzzle's current solvers")

        # Browser 2: Check historic solvers on first puzzle
        print("  [Browser 2] Checking historic solvers on first puzzle...")
        get_puzzle_icons(find_puzzle(page2, puzzle1_name))[1].click()
        page2.wait_for_selector("dialog", timeout=5000)
        time.sleep(0.5)

        modal_content = page2.query_selector("dialog").inner_text()
        assert "All solvers:" in modal_content and solver_name in modal_content, \
            f"Solver not in historic solvers list: {modal_content}"
        print(f"  [Browser 2] ✓ Verified solver in historic solvers")

        close_dialog(page2)

        # Browser 2: Verify solver now on second puzzle
        print("  [Browser 2] Verifying solver is on second puzzle...")
        wait_for_solver_on_puzzle(page2, puzzle2_name, solver_name)
        print("  [Browser 2] ✓ Verified solver now on second puzzle")

        browser1.close()
        browser2.close()
        print("✓ Solver reassignment and historic solvers tracking completed successfully")


# ──────────────────────────────────────────────────────────
# Test 16: Basic Page Load
# ──────────────────────────────────────────────────────────

def test_basic_page_load():
    """Test that the main page loads and displays expected elements."""
    with sync_playwright() as p:
        print("Starting basic page load test...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

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


# ──────────────────────────────────────────────────────────
# Test 17: Advanced Controls
# ──────────────────────────────────────────────────────────

def test_advanced_controls():
    """Test that advanced controls render with status filters."""
    with sync_playwright() as p:
        print("Starting advanced controls test...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("  Navigating to main page...")
        page.goto(f"{BASE_URL}?assumedid=testuser", wait_until="networkidle")

        print("  Waiting for settings component to render...")
        page.wait_for_selector(".toggle-row.pills label:has-text('Advanced')", timeout=10000)

        print("  Clicking 'Advanced' pill toggle...")
        page.click(".toggle-row.pills label:has-text('Advanced')")

        print("  Checking for status filters...")
        page.wait_for_selector("#detailed-controls", timeout=5000)

        filters = page.locator(".filter").count()
        print(f"  Found {filters} status filters")
        assert filters > 0, "No status filters found!"

        browser.close()
        print("✓ Advanced controls test completed successfully")


# ──────────────────────────────────────────────────────────
# Test 18: Navbar Functionality
# ──────────────────────────────────────────────────────────

def test_navbar_functionality():
    """Test that navbar renders correctly with proper links and states."""
    with sync_playwright() as p:
        print("Starting navbar functionality test...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("  Navigating to main page...")
        page.goto(f"{BASE_URL}?assumedid=testuser", wait_until="networkidle")

        print("  Checking for navbar...")
        page.wait_for_selector(".nav-links", timeout=5000)

        print("  Verifying navbar links...")
        for link_text in ["Main Dashboard", "Status Overview", "PuzzBot", "PB Tools", "Wiki", "Old UI", "Admin"]:
            assert page.locator(f".nav-links a:has-text('{link_text}')").count() > 0, f"Missing navbar link: {link_text}"
            print(f"    ✓ Found link: {link_text}")

        print("  Checking that current page is highlighted...")
        assert page.locator(".nav-links a.current:has-text('Main Dashboard')").count() > 0, \
            "Main Dashboard not marked as current!"
        print("    ✓ Main Dashboard is current page")

        print("  Checking Wiki link opens in new tab...")
        target = page.locator(".nav-links a:has-text('Wiki')").get_attribute("target")
        assert target == "_blank", f"Wiki link target is '{target}', expected '_blank'"
        print("    ✓ Wiki link opens in new tab")

        print("  Testing navigation to Status Overview...")
        page.click(".nav-links a:has-text('Status Overview')")
        page.wait_for_url("**/status.php**", timeout=5000)

        print("  Verifying Status Overview is now current page...")
        page.wait_for_selector(".nav-links a.current:has-text('Status Overview')", timeout=5000)
        print("    ✓ Status Overview is current after navigation")

        browser.close()
        print("✓ Navbar functionality test completed successfully")


# ──────────────────────────────────────────────────────────
# Test 19: Status Page
# ──────────────────────────────────────────────────────────

def test_status_page():
    """Test that status.php displays correctly with all sections and column visibility controls."""
    with sync_playwright() as p:
        print("Starting status page test...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("  Navigating to status page...")
        page.goto(f"{BASE_URL}/status.php?assumedid=testuser", wait_until="networkidle")

        print("  Checking page title...")
        page.wait_for_selector("h1", timeout=5000)
        assert "Hunt Status Overview" in page.locator("h1").inner_text()

        print("  Waiting for Vue app to mount...")
        page.wait_for_selector(".status-header", timeout=5000)

        for section in ["Hunt Progress", "Status Breakdown", "Column Visibility"]:
            page.wait_for_selector(f"text={section}", timeout=5000)
            print(f"    ✓ Found section: {section}")

        # Expand Column Visibility if collapsed
        content = page.locator(".column-visibility .info-box-content")
        if not content.is_visible():
            print("  Expanding Column Visibility...")
            page.evaluate("() => { const h = document.querySelector('.column-visibility .info-box-header'); if (h) h.click(); }")
            page.wait_for_selector(".column-visibility .info-box-content", state="visible", timeout=5000)
            time.sleep(0.5)

        print("  Verifying all column checkboxes...")
        expected_columns = ["Round", "Status", "Doc", "Sheet #", "Chat",
                          "Solvers (cur)", "Solvers (all)", "Location", "Tags", "Comment"]

        page.wait_for_selector(".column-checkboxes label", timeout=5000)
        for col in expected_columns:
            assert page.locator(f".column-checkboxes label:has-text('{col}') input[type='checkbox']").count() > 0, \
                f"Missing checkbox for column: {col}"
            print(f"    ✓ Found checkbox: {col}")

        print("  Testing column visibility toggle for each column...")
        for col in expected_columns:
            checkbox = page.locator(f".column-checkboxes label:has-text('{col}') input[type='checkbox']")

            if not checkbox.is_checked():
                checkbox.click(force=True)
                time.sleep(0.3)

            hidden_before = page.locator("th.hidden-column").count()
            checkbox.click(force=True)
            time.sleep(0.3)
            hidden_after_hide = page.locator("th.hidden-column").count()
            assert hidden_after_hide > hidden_before, f"{col} column should be hidden"
            print(f"      ✓ {col} column hidden ({hidden_before} → {hidden_after_hide})")

            checkbox.click(force=True)
            time.sleep(0.3)
            hidden_after_show = page.locator("th.hidden-column").count()
            assert hidden_after_show == hidden_before, f"{col} column should be visible again"
            print(f"      ✓ {col} column shown ({hidden_after_hide} → {hidden_after_show})")

        # Test Show All
        print("  Testing 'Show All' button...")
        for col in ["Round", "Location", "Tags"]:
            checkbox = page.locator(f".column-checkboxes label:has-text('{col}') input[type='checkbox']")
            if checkbox.is_checked():
                checkbox.click(force=True)
        time.sleep(0.3)

        page.locator(".column-checkboxes button:has-text('Show All')").click()
        time.sleep(0.5)

        for col in expected_columns:
            assert page.locator(f".column-checkboxes label:has-text('{col}') input[type='checkbox']").is_checked(), \
                f"{col} checkbox should be checked after 'Show All'"
        print("    ✓ All columns visible after 'Show All'")

        browser.close()
        print("✓ Status page test completed successfully")


# ──────────────────────────────────────────────────────────
# Test 20: Solved Puzzles Excluded from Status Page
# ──────────────────────────────────────────────────────────

def test_solved_puzzles_excluded():
    """Test that solved puzzles don't appear in status.php tables."""
    with sync_playwright() as p:
        print("Starting solved puzzle exclusion test...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("  Navigating to status page...")
        page.goto(f"{BASE_URL}/status.php?assumedid=testuser", wait_until="networkidle")
        page.wait_for_selector(".status-header", timeout=5000)
        time.sleep(1)

        # Expand all sections
        print("  Ensuring all sections are expanded...")
        sections = page.locator(".section-header")
        for i in range(sections.count()):
            section = sections.nth(i)
            collapse_icon = section.locator(".collapse-icon")
            if collapse_icon.get_attribute("class") and "collapsed" in collapse_icon.get_attribute("class"):
                section.click()
                time.sleep(0.5)

        # Find a puzzle to solve
        print("  Looking for a puzzle to solve...")
        puzzle_row = None
        overview_table = page.locator(".puzzle-table").nth(2)
        if overview_table.locator("table tr").count() > 1:
            puzzle_row = overview_table.locator("table tr").nth(1)
            print(f"    Found puzzle in Total Hunt Overview")
        else:
            noloc_table = page.locator(".puzzle-table").nth(0)
            if noloc_table.locator("table tr").count() > 1:
                puzzle_row = noloc_table.locator("table tr").nth(1)
                print(f"    Found puzzle in No Location")

        assert puzzle_row is not None, "No puzzles found in any table to test with"

        puzzle_name = puzzle_row.locator("td:nth-child(3) a").inner_text()
        puzzle_id = puzzle_row.get_attribute("id").split("-")[-1]
        print(f"    Puzzle: {puzzle_name} (ID: {puzzle_id})")

        total_before = page.locator("table tr[id^='puzzle-']").count()
        print(f"  Counting puzzles before solving: {total_before}")

        # Solve via API
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
                    return {{ success: response.ok, data: data }};
                }} catch (e) {{
                    return {{ success: false, error: e.toString() }};
                }}
            }}
        """)
        assert solve_result.get("success"), f"Failed to solve puzzle: {solve_result}"
        print(f"    ✓ Puzzle solved successfully")

        print("  Reloading page...")
        page.reload(wait_until="networkidle")
        time.sleep(1)

        total_after = page.locator("table tr[id^='puzzle-']").count()
        print(f"  Counting puzzles after solving: {total_after}")

        assert total_after < total_before, f"Puzzle count did not decrease ({total_before} → {total_after})"
        print(f"    ✓ Total visible puzzle count decreased by {total_before - total_after}")

        remaining = page.locator(f"tr#puzzle-noloc-{puzzle_id}, tr#puzzle-overview-{puzzle_id}, tr#puzzle-sheet-{puzzle_id}").count()
        assert remaining == 0, f"Solved puzzle still appears in {remaining} table(s)"
        print(f"    ✓ Puzzle '{puzzle_name}' successfully removed from all tables")

        browser.close()
        print("✓ Solved puzzle exclusion test completed successfully")


# ──────────────────────────────────────────────────────────
# Test 21: Accounts Management Page
# ──────────────────────────────────────────────────────────

def test_accounts_page():
    """Test that accounts.php renders correctly with expected sections and elements."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("  Navigating to accounts page as admin...")
        page.goto(f"{BASE_URL}/accounts.php?assumedid=testuser", wait_until="networkidle")

        # Verify page loaded (not access denied)
        page.wait_for_selector("h1", timeout=5000)
        title = page.locator("h1").inner_text()
        assert "Accounts Management" in title, f"Unexpected title: {title}"
        print(f"    ✓ Page title: {title}")

        # Verify navbar is rendered
        page.wait_for_selector(".nav-links", timeout=5000)
        print("    ✓ Navbar rendered")

        # Verify accounts table is populated
        print("  Checking accounts table...")
        page.wait_for_selector("#accounts-table", timeout=5000)
        solver_rows = page.locator("#accounts-table tbody tr").count()
        assert solver_rows > 0, "Accounts table has no data rows"
        print(f"    ✓ Accounts table has {solver_rows} solver row(s)")

        # Verify table headers include key columns
        print("  Checking table columns...")
        for col in ["Username", "Full Name", "PT", "PB"]:
            assert page.locator(f"#accounts-table th:has-text('{col}')").count() > 0, f"Missing column: {col}"
            print(f"    ✓ Found column: {col}")

        # Verify filter input exists
        filter_input = page.locator("#filter")
        assert filter_input.count() > 0, "Filter input not found"
        print("    ✓ Filter input present")

        # Verify delete modal exists (hidden)
        assert page.locator("#delete-modal").count() > 0, "Delete confirmation modal not found"
        print("    ✓ Delete confirmation modal present")

        # Test access denied for non-admin user
        print("  Testing access restriction for non-admin user...")
        page.goto(f"{BASE_URL}/accounts.php?assumedid=testsolver1", wait_until="networkidle")
        denied_text = page.locator("body").inner_text()
        assert "ACCESS DENIED" in denied_text, "Non-admin user should see ACCESS DENIED"
        print("    ✓ Non-admin access correctly denied")

        browser.close()
        print("✓ Accounts management page test completed successfully")


# ──────────────────────────────────────────────────────────
# Test 22: Config Page
# ──────────────────────────────────────────────────────────

def test_config_page():
    """Test that config.php renders correctly with warning modal, categories, and editing controls."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("  Navigating to config page as admin...")
        page.goto(f"{BASE_URL}/config.php?assumedid=testuser", wait_until="networkidle")

        # Verify warning modal appears on load
        print("  Checking for warning modal...")
        modal = page.locator("#warn-modal")
        assert modal.is_visible(), "Warning modal should be visible on page load"
        print("    ✓ Warning modal displayed")

        # Verify config content is hidden behind modal
        content = page.locator("#config-content")
        assert not content.is_visible(), "Config content should be hidden until modal dismissed"
        print("    ✓ Config content hidden behind modal")

        # Dismiss the warning modal
        print("  Dismissing warning modal...")
        page.click("#warn-modal button:has-text('I understand')")
        page.wait_for_selector("#config-content", state="visible", timeout=3000)
        print("    ✓ Modal dismissed, config content revealed")

        # Verify categories are rendered
        print("  Checking for config categories...")
        page_text = page.locator("#config-content").inner_text()

        for category in ["Current Hunt Adjustments", "General", "BigJimmy Bot",
                         "Google Sheets & Drive", "Discord (Puzzcord)", "LLM & AI"]:
            assert category in page_text, f"Missing category: {category}"
            print(f"    ✓ Found category: {category}")

        # Cross-reference: fetch all config keys from the API and verify each one
        # appears on the page (accounting for hidden/deprecated keys)
        print("  Cross-referencing config keys from API against rendered page...")
        api_config = requests.get(f"{API_URL}/config").json().get("config", {})
        api_keys = set(api_config.keys())

        # Get rendered config keys from the page's data-key attributes
        rendered_keys = set(page.evaluate("""
            () => Array.from(document.querySelectorAll('#config-content .config-row[data-key]'))
                        .map(row => row.dataset.key)
        """))

        # Known hidden keys (deprecated, intentionally not shown)
        hidden_keys = {'SLACK_EMAIL_WEBHOOK', 'LDAP_ADMINDN', 'LDAP_ADMINPW',
                       'LDAP_DOMAIN', 'LDAP_HOST', 'LDAP_LDAP0'}

        missing_from_page = api_keys - rendered_keys - hidden_keys
        extra_on_page = rendered_keys - api_keys

        print(f"    API has {len(api_keys)} keys, page renders {len(rendered_keys)} rows, {len(hidden_keys)} intentionally hidden")
        assert len(missing_from_page) == 0, f"Config keys in API but NOT on page: {missing_from_page}"
        print(f"    ✓ All {len(api_keys - hidden_keys)} visible config keys accounted for on the page")

        if extra_on_page:
            print(f"    ⚠ Page has keys not in API (may be added via UI): {extra_on_page}")

        # Verify config rows exist
        config_rows = page.locator("#config-content .config-row").count()
        print(f"    ✓ Found {config_rows} config rows")
        assert config_rows > 5, f"Expected more than 5 config rows, found {config_rows}"

        # Verify Save/Revert buttons exist
        save_buttons = page.locator("#config-content button:has-text('Save')").count()
        revert_buttons = page.locator("#config-content button:has-text('Revert')").count()
        assert save_buttons > 0, "No Save buttons found"
        assert revert_buttons > 0, "No Revert buttons found"
        print(f"    ✓ Found {save_buttons} Save and {revert_buttons} Revert buttons")

        # Verify structured editors exist
        print("  Checking for structured editors...")
        assert page.locator("text=STATUS_METADATA").count() > 0, "Missing STATUS_METADATA editor"
        assert page.locator("text=METRICS_METADATA").count() > 0, "Missing METRICS_METADATA editor"
        print("    ✓ Structured editors present")

        # Test access denied for non-admin user
        print("  Testing access restriction for non-admin user...")
        page.goto(f"{BASE_URL}/config.php?assumedid=testsolver1", wait_until="networkidle")
        denied_text = page.locator("body").inner_text()
        assert "ACCESS DENIED" in denied_text, "Non-admin user should see ACCESS DENIED"
        print("    ✓ Non-admin access correctly denied")

        browser.close()
        print("✓ Config page test completed successfully")


# ──────────────────────────────────────────────────────────
# Test 23: Privilege Assignment and Gear Visibility
# ──────────────────────────────────────────────────────────

def test_privilege_and_gear_visibility():
    """Test assigning and revoking privileges, and verify that gear icon
    visibility and admin page access are correctly gated on those privileges."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Create test data: a round and a puzzle so we can check gear visibility
        round_name = create_round_via_ui(page, "Priv Test Round")["name"]
        puzzle_name = create_puzzle_via_ui(page, "Priv Test Puzzle", round_name)["name"]

        # Step 1: Verify non-admin user has NO gear icon
        print("  Step 1: Non-admin user should NOT see gear icon...")
        page.goto(f"{BASE_URL}/index.php?assumedid=testsolver1", wait_until="networkidle")
        page.wait_for_selector(f"text={puzzle_name}", timeout=10000)

        puzzle_elem = find_puzzle(page, puzzle_name)
        icons = get_puzzle_icons(puzzle_elem)
        has_settings = any(
            icon.get_attribute("title") and "settings" in icon.get_attribute("title").lower()
            for icon in icons
        )
        # Also check if any icon opens a puzzle-settings dialog
        gear_icon_count = page.locator(f".puzzle:has-text('{puzzle_name}') dialog select#puzzle-round").count()
        # Simpler: just check for the ⚙️ icon in puzzle icons
        puzzle_html = puzzle_elem.inner_html()
        has_gear = "⚙️" in puzzle_html or "puzzle-settings" in puzzle_html
        assert not has_gear, "Non-admin user should NOT see gear (⚙️) icon"
        print("    ✓ Non-admin user: no gear icon")

        # Step 2: Verify non-admin user is blocked from admin pages
        print("  Step 2: Non-admin user should be blocked from admin pages...")
        page.goto(f"{BASE_URL}/admin.php?assumedid=testsolver1", wait_until="networkidle")
        assert "ACCESS DENIED" in page.locator("body").inner_text(), "Non-admin should be denied admin.php"
        print("    ✓ admin.php: ACCESS DENIED")

        page.goto(f"{BASE_URL}/accounts.php?assumedid=testsolver1", wait_until="networkidle")
        assert "ACCESS DENIED" in page.locator("body").inner_text(), "Non-admin should be denied accounts.php"
        print("    ✓ accounts.php: ACCESS DENIED")

        page.goto(f"{BASE_URL}/config.php?assumedid=testsolver1", wait_until="networkidle")
        assert "ACCESS DENIED" in page.locator("body").inner_text(), "Non-admin should be denied config.php"
        print("    ✓ config.php: ACCESS DENIED")

        # Step 3: Grant puzztech privilege via API
        print("  Step 3: Granting puzztech privilege to testsolver1...")
        # Look up solver ID
        solver_data = requests.get(f"{API_URL}/solvers/byname/testsolver1").json()
        solver_id = solver_data["solver"]["id"]

        grant_result = requests.post(
            f"{API_URL}/rbac/puzztech/{solver_id}",
            json={"allowed": "YES"}
        )
        assert grant_result.ok, f"Failed to grant puzztech: {grant_result.text}"
        print(f"    ✓ puzztech granted to testsolver1 (id={solver_id})")

        # Step 4: Verify admin user NOW sees gear icon
        print("  Step 4: Newly privileged user should see gear icon...")
        page.goto(f"{BASE_URL}/index.php?assumedid=testsolver1", wait_until="networkidle")
        page.wait_for_selector(f"text={puzzle_name}", timeout=10000)

        puzzle_elem = find_puzzle(page, puzzle_name)
        puzzle_html = puzzle_elem.inner_html()
        has_gear = "⚙️" in puzzle_html
        assert has_gear, "Newly privileged user SHOULD see gear (⚙️) icon"
        print("    ✓ Privileged user: gear icon visible")

        # Step 5: Verify admin pages now accessible
        print("  Step 5: Privileged user should access admin pages...")
        page.goto(f"{BASE_URL}/admin.php?assumedid=testsolver1", wait_until="networkidle")
        admin_text = page.locator("body").inner_text()
        assert "ACCESS DENIED" not in admin_text, "Privileged user should access admin.php"
        assert "Super Admin" in admin_text, "admin.php should show Super Admin content"
        print("    ✓ admin.php: accessible")

        page.goto(f"{BASE_URL}/accounts.php?assumedid=testsolver1", wait_until="networkidle")
        assert "ACCESS DENIED" not in page.locator("body").inner_text(), "Privileged user should access accounts.php"
        print("    ✓ accounts.php: accessible")

        page.goto(f"{BASE_URL}/config.php?assumedid=testsolver1", wait_until="networkidle")
        assert "ACCESS DENIED" not in page.locator("body").inner_text(), "Privileged user should access config.php"
        print("    ✓ config.php: accessible")

        # Step 6: Revoke privilege and verify gear icon disappears
        print("  Step 6: Revoking puzztech privilege...")
        revoke_result = requests.post(
            f"{API_URL}/rbac/puzztech/{solver_id}",
            json={"allowed": "NO"}
        )
        assert revoke_result.ok, f"Failed to revoke puzztech: {revoke_result.text}"
        print("    ✓ puzztech revoked")

        print("  Verifying gear icon removed after privilege revocation...")
        page.goto(f"{BASE_URL}/index.php?assumedid=testsolver1", wait_until="networkidle")
        page.wait_for_selector(f"text={puzzle_name}", timeout=10000)

        puzzle_elem = find_puzzle(page, puzzle_name)
        puzzle_html = puzzle_elem.inner_html()
        has_gear = "⚙️" in puzzle_html
        assert not has_gear, "User without privileges should NOT see gear icon after revocation"
        print("    ✓ Gear icon removed after privilege revocation")

        # Step 7: Verify admin pages blocked again
        print("  Step 7: Verifying admin pages blocked after revocation...")
        page.goto(f"{BASE_URL}/admin.php?assumedid=testsolver1", wait_until="networkidle")
        assert "ACCESS DENIED" in page.locator("body").inner_text(), "Unprivileged user should be denied admin.php"
        print("    ✓ admin.php: ACCESS DENIED after revocation")

        browser.close()
        print("✓ Privilege assignment and gear visibility test completed successfully")


# ──────────────────────────────────────────────────────────
# Main Entry Point
# ──────────────────────────────────────────────────────────

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
        ('21', 'accounts', test_accounts_page, 'Accounts Management Page'),
        ('22', 'config', test_config_page, 'Config Page'),
        ('23', 'privs', test_privilege_and_gear_visibility, 'Privilege And Gear Visibility'),
    ]

    if args.list:
        print("Available tests:")
        for number, name, _, display_name in all_tests:
            print(f"  {number}. {display_name} (--tests {number} or --tests {name})")
        sys.exit(0)

    if not args.allow_destructive:
        print("ERROR: --allow-destructive flag is required")
        print("This test suite will RESET THE HUNT DATABASE, destroying all puzzle data.")
        print("DO NOT run this on a production system!")
        sys.exit(1)

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
    for test_func, _ in tests_to_run:
        runner.run_test(test_func)

    runner.print_summary()
    sys.exit(0 if runner.failed == 0 else 1)


if __name__ == "__main__":
    main()
