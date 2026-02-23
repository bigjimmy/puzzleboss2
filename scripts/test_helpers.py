"""
Shared test infrastructure for PuzzleBoss test suites.

Provides constants, base classes, assertion helpers, browser context managers,
and the MainPage page object for UI tests. Used by both test_api_coverage.py
and test_ui_comprehensive.py.
"""

import argparse
import os
import subprocess
import sys
import time
import traceback
from contextlib import contextmanager

import requests

# ============================================================================
# Constants
# ============================================================================

BASE_URL = "http://localhost"  # Web frontend (UI tests)
API_URL = os.environ.get("API_BASE_URL", "http://localhost:5000")  # REST API

# Playwright timeouts (milliseconds)
REFRESH_TIMEOUT = 7000  # auto-refresh polling
DIALOG_TIMEOUT = 5000  # modal open/close
PAGE_LOAD_TIMEOUT = 10000  # full page load
CREATION_TIMEOUT = 30000  # puzzle 5-step creation flow
NAV_TIMEOUT = 15000  # navigation


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
# Assertion helpers — return False on failure (caller does early return)
# ============================================================================


def assert_eq(result, actual, expected, msg):
    """Assert actual == expected. Returns False (and calls result.fail) on mismatch."""
    if actual != expected:
        result.fail(f"{msg}: expected {expected!r}, got {actual!r}")
        return False
    return True


def assert_field(result, data, field, expected, msg_prefix=""):
    """Assert data[field] == expected. Returns False on mismatch or missing field."""
    actual = data.get(field) if isinstance(data, dict) else getattr(data, field, None)
    if actual != expected:
        label = f"{msg_prefix} " if msg_prefix else ""
        result.fail(f"{label}{field}: expected {expected!r}, got {actual!r}")
        return False
    return True


def assert_in(result, item, container, msg):
    """Assert item in container. Returns False on failure."""
    if item not in container:
        result.fail(f"{msg}: {item!r} not found in {container!r}")
        return False
    return True


def assert_true(result, condition, msg):
    """Assert condition is truthy. Returns False on failure."""
    if not condition:
        result.fail(msg)
        return False
    return True


# ============================================================================
# Entity lookup helper
# ============================================================================


def find_by_name(items, name, key="name"):
    """Find the first dict in items where dict[key] == name. Returns None if not found."""
    for item in items:
        if item.get(key) == name:
            return item
    return None


# ============================================================================
# Test runner base
# ============================================================================


class TestRunnerBase:
    """Shared runner for both API and UI test suites.

    API tests use ``use_result_object=True`` which passes a TestResult to
    each test callable.  UI tests use ``use_result_object=False`` where
    exceptions signal failure.
    """

    def __init__(self):
        self.results = []  # list of (name, passed, duration, message)

    def run_test(self, name, test_callable, use_result_object=False):
        """Run a single test and record its outcome.

        Args:
            name: Display name for the test.
            test_callable: The test function. If *use_result_object* is True
                           it receives a ``TestResult`` as its sole argument;
                           otherwise it takes no arguments.
            use_result_object: API-style (True) vs UI-style (False).
        """
        print(f"\n{'=' * 70}")
        print(f"TEST: {name}")
        print(f"{'=' * 70}")

        start = time.time()
        if use_result_object:
            result = TestResult()
            try:
                test_callable(result)
            except Exception as e:
                result.fail(f"Unhandled exception: {e}")
                traceback.print_exc()
            elapsed = time.time() - start
            status = "✅" if result.passed else "❌"
            print(f"\n{status} {name}: {result.message} ({elapsed:.2f}s)")
            self.results.append((name, result.passed, elapsed, result.message))
        else:
            try:
                test_callable()
                elapsed = time.time() - start
                print(f"✅ PASSED ({elapsed:.2f}s)")
                self.results.append((name, True, elapsed, ""))
            except Exception as e:
                elapsed = time.time() - start
                print(f"❌ FAILED: {e}")
                traceback.print_exc()
                self.results.append((name, False, elapsed, str(e)))

    def print_summary(self):
        """Print the pass/fail summary table."""
        print(f"\n{'=' * 70}")
        print("TEST RESULTS SUMMARY")
        print(f"{'=' * 70}")

        passed = failed = 0
        for name, ok, duration, message in self.results:
            icon = "✅" if ok else "❌"
            suffix = f": {message}" if message else ""
            print(f"{icon} {name}{suffix} ({duration:.2f}s)")
            if ok:
                passed += 1
            else:
                failed += 1

        total_duration = sum(d for _, _, d, _ in self.results)
        print(f"\nTotal: {len(self.results)} tests")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Duration: {total_duration:.2f}s")
        print(f"{'=' * 70}")

    @property
    def all_passed(self):
        return all(ok for _, ok, _, _ in self.results)


# ============================================================================
# Setup helpers
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
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"WARNING: Reset failed: {result.stderr}")
    else:
        print("Hunt reset completed successfully")
    time.sleep(3)  # Wait for database to settle


def ensure_test_solvers_api(base_url, count=10):
    """Ensure enough numbered test solvers exist (for API tests)."""
    try:
        r = requests.get(f"{base_url}/solvers")
        solvers = r.json().get("solvers", [])
        existing = len(solvers)
        if existing >= count:
            print(f"  Sufficient solvers available ({existing} >= {count})")
            return
        for i in range(count - existing):
            name = f"testuser{existing + i + 1}"
            requests.post(
                f"{base_url}/solvers",
                json={"name": name, "fullname": f"Test User {existing + i + 1}"},
            )
        print(f"  Created {count - existing} additional test solvers")
    except Exception as e:
        print(f"  Warning: Could not ensure test solvers: {e}")


def ensure_test_solvers_ui(api_url=API_URL):
    """Ensure named test solvers testsolver1..5 exist (for UI tests)."""
    print("Checking for test solvers...")
    try:
        response = requests.get(f"{api_url}/solvers")
        solvers = response.json().get("solvers", [])
        existing_names = {s["name"] for s in solvers}

        created = 0
        for i in range(1, 6):
            name = f"testsolver{i}"
            if name not in existing_names:
                try:
                    requests.post(
                        f"{api_url}/solvers",
                        json={"name": name, "fullname": f"Test Solver {i}"},
                    )
                    created += 1
                except Exception:
                    pass  # May already exist

        if created:
            print(f"  Created {created} test solvers (testsolver1..5)")
        else:
            print("  All test solvers already exist")

        response = requests.get(f"{api_url}/solvers")
        solvers = response.json().get("solvers", [])
        print(f"  Total solvers available: {len(solvers)}")
    except Exception as e:
        print(f"Warning: Could not ensure test solvers: {e}")


# ============================================================================
# CLI helpers
# ============================================================================


def make_arg_parser(description, test_names):
    """Create an ArgumentParser with --allow-destructive, --tests, and --list."""
    parser = argparse.ArgumentParser(
        description=description,
        epilog="WARNING: This script will RESET THE HUNT DATABASE!",
    )
    parser.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Required flag to confirm destructive database operations",
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        help="Run specific tests (by number or name). Examples: --tests 1 3 7, --tests 1,3,7",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available tests and exit",
    )
    return parser


def resolve_selected_tests(args, all_tests, test_names=None):
    """Parse --tests specs into a set of 1-based test indices, or None for all.

    *all_tests* is the list of (number/index, name, func, display_name) tuples
    used by the UI runner; for the API runner pass *test_names* (a list of
    display names) and *all_tests=None*.

    Returns a set of 1-based indices or None (meaning "run all").
    """
    if not args.tests:
        return None

    # Flatten: support both "--tests 1 3 7" and "--tests 1,3,7" (or mixed)
    specs = []
    for arg in args.tests:
        specs.extend(arg.split(","))
    specs = [s.strip() for s in specs if s.strip()]

    selected = set()
    if all_tests is not None:
        # UI-style: each entry is (number_str, short_name, func, display_name)
        for spec in specs:
            spec_lower = spec.lower()
            found = False
            for number, name, _func, _display in all_tests:
                if spec == number or spec_lower == name.lower():
                    selected.add(int(number))
                    found = True
                    break
            if not found:
                print(f"ERROR: Unknown test '{spec}'")
                print("Use --list to see available tests")
                sys.exit(1)
    else:
        # API-style: specs are 1-based integers
        for spec in specs:
            try:
                idx = int(spec)
            except ValueError:
                print(f"ERROR: Invalid test number '{spec}'")
                sys.exit(1)
            if idx < 1 or idx > len(test_names):
                print(f"ERROR: Test number {idx} out of range (1-{len(test_names)})")
                sys.exit(1)
            selected.add(idx)

    return selected


def handle_list_and_destructive(args, test_names=None, all_tests=None):
    """Handle --list and --allow-destructive checks.  Exits if applicable.

    Pass *test_names* (list of strings) for API-style, or *all_tests*
    (list of tuples) for UI-style.
    """
    if args.list:
        if all_tests is not None:
            print("Available tests:")
            for number, name, _, display_name in all_tests:
                print(f"  {number}. {display_name} (--tests {number} or --tests {name})")
        elif test_names is not None:
            for i, name in enumerate(test_names, 1):
                print(f"  {i:2d}. {name}")
        sys.exit(0)

    if not args.allow_destructive:
        print("ERROR: This test suite modifies the database.")
        print("Run with --allow-destructive to confirm.")
        sys.exit(1)


# ============================================================================
# Browser context managers (Playwright)
# ============================================================================


@contextmanager
def playwright_browser(headless=True):
    """Yield (playwright, browser). Auto-closes on exit.

    Usage::

        with playwright_browser() as (p, browser):
            page = browser.new_page()
            ...
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            yield p, browser
        finally:
            browser.close()


@contextmanager
def playwright_browsers(count=2, headless=True):
    """Yield (playwright, browser1, browser2, ...). Auto-closes all.

    Usage::

        with playwright_browsers(2) as (p, b1, b2):
            page1, page2 = b1.new_page(), b2.new_page()
            ...
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browsers = [p.chromium.launch(headless=headless) for _ in range(count)]
        try:
            yield (p, *browsers)
        finally:
            for b in browsers:
                b.close()


# ============================================================================
# MainPage — Page Object for index.php
# ============================================================================


class MainPage:
    """Page Object encapsulating interactions with the main Puzzleboss dashboard.

    Consolidates the ~20 standalone UI helper functions and ~19 inline
    ``wait_for_function`` JavaScript blocks into named methods.
    """

    def __init__(self, page, base_url=BASE_URL):
        self.page = page
        self.base_url = base_url

    # ── Navigation ──────────────────────────────────────────

    def goto(self, user="testuser"):
        """Navigate to index.php as the given user."""
        self.page.goto(f"{self.base_url}/index.php?assumedid={user}")

    # ── Finders ─────────────────────────────────────────────

    def find_puzzle(self, name):
        """Find a puzzle element by name text. Raises AssertionError if not found."""
        for puzzle in self.page.locator(".puzzle").all():
            if name in puzzle.inner_text():
                return puzzle
        raise AssertionError(f"Puzzle '{name}' not found in UI")

    def find_round_header(self, name):
        """Find a round header by name text. Raises AssertionError if not found."""
        for header in self.page.locator(".round-header").all():
            if name in header.inner_text():
                return header
        raise AssertionError(f"Round header '{name}' not found in UI")

    def get_puzzle_icons(self, puzzle_elem):
        """Get .puzzle-icon elements. Order: 0=status, 1=workstate, 2=📊, 3=🗣️, 4=note-tags, 5=settings."""
        return puzzle_elem.locator(".puzzle-icon").all()

    # ── Puzzle interactions ─────────────────────────────────

    def change_puzzle_status(self, puzzle_elem, status):
        """Open the status modal and select a new status. Does NOT save/close."""
        icons = self.get_puzzle_icons(puzzle_elem)
        assert len(icons) > 0, "No puzzle icons found"
        icons[0].click()
        self.page.wait_for_selector("dialog select.dropdown", timeout=DIALOG_TIMEOUT)
        self.page.select_option("dialog select.dropdown", status)

    def solve_puzzle(self, puzzle_elem, answer):
        """Solve via UI: open status modal → Solved → fill answer → save."""
        self.change_puzzle_status(puzzle_elem, "Solved")
        time.sleep(0.5)
        answer_input = self.page.locator("dialog p:has-text('Answer:') input")
        assert answer_input.count() > 0, "Answer input not found in dialog"
        answer_input.fill(answer)
        self.save_and_close_dialog()

    def claim_puzzle(self, puzzle_elem):
        """Click the workstate icon and claim the puzzle."""
        icons = self.get_puzzle_icons(puzzle_elem)
        assert len(icons) > 1, "Not enough puzzle icons for workstate"
        icons[1].click()
        self.page.wait_for_selector("dialog", timeout=DIALOG_TIMEOUT)
        time.sleep(0.5)
        yes_button = self.page.locator("dialog button:has-text('Yes')")
        if yes_button.count() > 0:
            yes_button.click()
        else:
            save = self.page.locator("dialog button:has-text('Save')")
            if save.count() > 0:
                save.click()
            else:
                self.page.click("dialog button:has-text('Close')")
        self.page.wait_for_selector("dialog", state="hidden", timeout=DIALOG_TIMEOUT)

    def add_tag_to_puzzle(self, puzzle_elem, tag_name):
        """Open the note-tags modal and add a tag."""
        icons = self.get_puzzle_icons(puzzle_elem)
        assert len(icons) > 4, f"Not enough puzzle icons for note-tags (found {len(icons)})"
        icons[4].click()
        self.page.wait_for_selector("dialog", timeout=DIALOG_TIMEOUT)
        tag_input = self.page.locator("dialog input[list='taglist']")
        assert tag_input.count() > 0, "Tag input not found in dialog"
        tag_input.fill(tag_name)
        add_button = self.page.locator("dialog span.puzzle-icon:has-text('➕')")
        assert add_button.count() > 0, "Add tag button (➕) not found"
        add_button.click()
        time.sleep(0.5)
        self.save_and_close_dialog()

    # ── Dialog helpers ──────────────────────────────────────

    def save_and_close_dialog(self):
        """Click Save and wait for the dialog to close."""
        self.page.click("dialog button:has-text('Save')")
        self.page.wait_for_selector("dialog", state="hidden", timeout=DIALOG_TIMEOUT)

    def close_dialog(self):
        """Click Close and wait for the dialog to close."""
        self.page.click("dialog button:has-text('Close')")
        self.page.wait_for_selector("dialog", state="hidden", timeout=DIALOG_TIMEOUT)

    def save_settings_dialog(self):
        """Save the gear modal with its two-step confirmation flow."""
        self.page.click("dialog button:has-text('Save Changes')")
        self.page.wait_for_selector("dialog .confirm-banner", timeout=3000)
        self.page.click("dialog button:has-text('Yes, Save')")
        self.page.wait_for_selector("dialog", state="hidden", timeout=DIALOG_TIMEOUT)

    # ── Settings ────────────────────────────────────────────

    def enable_all_puzzle_filters(self):
        """Enable all puzzle status filters via localStorage and reload."""
        self.page.evaluate("""() => {
            const settings = JSON.parse(localStorage.getItem('settings') || '{}');
            if (!settings.puzzleFilter) settings.puzzleFilter = {};
            const statuses = ['New', 'Being worked', 'Needs eyes', 'Solved', 'Critical',
                            'Unnecessary', 'WTF', 'Under control', 'Waiting for HQ',
                            'Grind', 'Abandoned', 'Speculative'];
            statuses.forEach(s => settings.puzzleFilter[s] = true);
            localStorage.setItem('settings', JSON.stringify(settings));
            location.reload();
        }""")

    # ── Wait helpers ────────────────────────────────────────

    def wait_for_puzzle_status(self, puzzle_name, status, timeout=REFRESH_TIMEOUT):
        """Wait for auto-refresh to show a specific status on a puzzle."""
        self.page.wait_for_function(
            f"""() => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{puzzle_name}')) {{
                        const statusIcon = puzzle.querySelector('.puzzle-icon');
                        return statusIcon && statusIcon.title.includes('{status}');
                    }}
                }}
                return false;
            }}""",
            timeout=timeout,
        )

    def wait_for_round_solved(self, round_name, timeout=REFRESH_TIMEOUT):
        """Wait for auto-refresh to mark a round as solved."""
        self.page.wait_for_function(
            f"""() => {{
                const headers = document.querySelectorAll('.round-header');
                for (let header of headers) {{
                    if (header.innerText.includes('{round_name}') && header.classList.contains('solved')) {{
                        return true;
                    }}
                }}
                return false;
            }}""",
            timeout=timeout,
        )

    def wait_for_solver_on_puzzle(self, puzzle_name, solver_name, timeout=REFRESH_TIMEOUT):
        """Wait for auto-refresh to show a solver on a puzzle's workstate tooltip."""
        self.page.wait_for_function(
            f"""() => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{puzzle_name}')) {{
                        const icons = puzzle.querySelectorAll('.puzzle-icon');
                        const workstateIcon = icons[1];
                        return workstateIcon && workstateIcon.title.includes('{solver_name}');
                    }}
                }}
                return false;
            }}""",
            timeout=timeout,
        )

    def wait_for_solver_removed(self, puzzle_name, solver_name, timeout=REFRESH_TIMEOUT):
        """Wait for auto-refresh to show a solver removed from a puzzle."""
        self.page.wait_for_function(
            f"""() => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{puzzle_name}')) {{
                        const icons = puzzle.querySelectorAll('.puzzle-icon');
                        const workstateIcon = icons[1];
                        return workstateIcon && !workstateIcon.title.includes('{solver_name}');
                    }}
                }}
                return false;
            }}""",
            timeout=timeout,
        )

    def wait_for_answer_text(self, puzzle_name, answer, timeout=REFRESH_TIMEOUT):
        """Wait for auto-refresh to show an answer on a puzzle."""
        self.page.wait_for_function(
            f"""() => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{puzzle_name}')) {{
                        const answerElem = puzzle.querySelector('.answer');
                        return answerElem && answerElem.innerText.includes('{answer}');
                    }}
                }}
                return false;
            }}""",
            timeout=timeout,
        )

    def wait_for_solver_reassignment(self, old_puzzle, new_puzzle, solver_name, timeout=REFRESH_TIMEOUT):
        """Wait for auto-refresh to show solver moved from old_puzzle to new_puzzle."""
        self.page.wait_for_function(
            f"""() => {{
                const puzzles = document.querySelectorAll('.puzzle');
                let oldClear = false;
                let newHas = false;
                for (let puzzle of puzzles) {{
                    const text = puzzle.innerText;
                    const icons = puzzle.querySelectorAll('.puzzle-icon');
                    const workstateIcon = icons[1];
                    if (workstateIcon) {{
                        if (text.includes('{old_puzzle}') && !workstateIcon.title.includes('{solver_name}')) oldClear = true;
                        if (text.includes('{new_puzzle}') && workstateIcon.title.includes('{solver_name}')) newHas = true;
                    }}
                }}
                return oldClear && newHas;
            }}""",
            timeout=timeout,
        )

    def wait_for_puzzle_in_round(self, puzzle_name, round_name, timeout=REFRESH_TIMEOUT):
        """Wait for auto-refresh to show a puzzle within a specific round."""
        self.page.wait_for_function(
            f"""() => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const headerText = round.querySelector('.round-header')?.innerText || '';
                    if (headerText.includes('{round_name}')) {{
                        const bodyText = round.querySelector('.round-body')?.innerText || '';
                        return bodyText.includes('{puzzle_name}');
                    }}
                }}
                return false;
            }}""",
            timeout=timeout,
        )

    def wait_for_puzzle_not_in_round(self, puzzle_name, round_name, timeout=REFRESH_TIMEOUT):
        """Wait for auto-refresh to confirm a puzzle is NOT in a specific round."""
        self.page.wait_for_function(
            f"""() => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const headerText = round.querySelector('.round-header')?.innerText || '';
                    if (headerText.includes('{round_name}')) {{
                        const bodyText = round.querySelector('.round-body')?.innerText || '';
                        return !bodyText.includes('{puzzle_name}');
                    }}
                }}
                return true;
            }}""",
            timeout=timeout,
        )

    def wait_for_puzzle_moved(self, puzzle_name, from_round, to_round, timeout=REFRESH_TIMEOUT):
        """Wait for auto-refresh to show puzzle moved between rounds."""
        self.page.wait_for_function(
            f"""() => {{
                const rounds = document.querySelectorAll('.round');
                let inNew = false;
                let notInOld = true;
                for (let round of rounds) {{
                    const headerText = round.querySelector('.round-header')?.innerText || '';
                    const bodyText = round.querySelector('.round-body')?.innerText || '';
                    if (headerText.includes('{to_round}') && bodyText.includes('{puzzle_name}')) inNew = true;
                    if (headerText.includes('{from_round}') && bodyText.includes('{puzzle_name}')) notInOld = false;
                }}
                return inNew && notInOld;
            }}""",
            timeout=timeout,
        )

    def wait_for_puzzle_name(self, new_name, timeout=REFRESH_TIMEOUT):
        """Wait for auto-refresh to show a puzzle with the given name."""
        self.page.wait_for_function(
            f"""() => {{
                const puzzles = document.querySelectorAll('.puzzle');
                for (let puzzle of puzzles) {{
                    if (puzzle.innerText.includes('{new_name}')) return true;
                }}
                return false;
            }}""",
            timeout=timeout,
        )

    def wait_for_round_collapsed(self, round_name, timeout=REFRESH_TIMEOUT):
        """Wait for a round's body to have the 'hiding' class."""
        self.page.wait_for_function(
            f"""() => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const header = round.querySelector('.round-header');
                    if (header && header.innerText.includes('{round_name}')) {{
                        const body = round.querySelector('.round-body');
                        return body && body.classList.contains('hiding');
                    }}
                }}
                return false;
            }}""",
            timeout=timeout,
        )

    def wait_for_round_expanded(self, round_name, timeout=REFRESH_TIMEOUT):
        """Wait for a round's body to NOT have the 'hiding' class."""
        self.page.wait_for_function(
            f"""() => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const header = round.querySelector('.round-header');
                    if (header && header.innerText.includes('{round_name}')) {{
                        const body = round.querySelector('.round-body');
                        return body && !body.classList.contains('hiding');
                    }}
                }}
                return false;
            }}""",
            timeout=timeout,
        )

    def click_round_header(self, round_name):
        """Click a round header by name (via JavaScript)."""
        self.page.evaluate(
            f"""() => {{
                const rounds = document.querySelectorAll('.round');
                for (let round of rounds) {{
                    const header = round.querySelector('.round-header');
                    if (header && header.innerText.includes('{round_name}')) {{ header.click(); return true; }}
                }}
                return false;
            }}"""
        )


# ============================================================================
# UI Creation helpers (standalone — use addround.php / addpuzzle.php)
# ============================================================================


def create_round_via_ui(page, round_name, base_url=BASE_URL):
    """Create a round using the addround.php form. Returns {"name": sanitized}."""
    timestamp = str(int(time.time()))
    unique_name = f"{round_name}{timestamp}"

    page.goto(f"{base_url}/addround.php?assumedid=testuser")
    page.fill("input[name='name']", unique_name)
    page.click("input[type='submit'][value='Add Round']")
    page.wait_for_selector("div.success", timeout=PAGE_LOAD_TIMEOUT)

    return {"name": unique_name.replace(" ", "")}


def create_puzzle_via_ui(page, puzzle_name, round_name, is_meta=False, is_speculative=False, base_url=BASE_URL):
    """Create a puzzle using the addpuzzle.php 5-step workflow. Returns {"name": sanitized}."""
    page.goto(f"{base_url}/addpuzzle.php?assumedid=testuser")
    page.wait_for_selector("input[name='name']", timeout=PAGE_LOAD_TIMEOUT)

    page.fill("input[name='name']", puzzle_name)
    page.fill("input[name='puzzle_uri']", f"https://example.com/{puzzle_name.replace(' ', '_')}")
    page.select_option("select[name='round_id']", label=round_name)

    if is_meta:
        page.check("input[name='is_meta']")
    if is_speculative:
        page.check("input[name='is_speculative']")

    page.click("input[type='submit'][value='Add New Puzzle']")
    page.wait_for_selector("#step5 .status:has-text('✅')", timeout=CREATION_TIMEOUT)

    return {"name": puzzle_name.replace(" ", "")}
