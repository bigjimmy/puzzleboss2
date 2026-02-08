#!/usr/bin/env python3
"""
Simple Playwright UI test example for Puzzleboss.

This demonstrates how to use Playwright for headless browser testing
to verify UI functionality. Useful for debugging frontend issues.

Usage:
    python scripts/test_ui_playwright.py

Requirements:
    - Docker container running (docker-compose up)
    - Or local dev server on http://localhost
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import sys
import time


def test_basic_page_load():
    """Test that the main page loads and displays expected elements."""
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Enable console logging from browser
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))

        try:
            print("Navigating to main page...")
            page.goto("http://localhost?assumedid=testuser", wait_until="networkidle")

            print("Checking page title...")
            assert "Puzzboss 2000" in page.title(), f"Unexpected title: {page.title()}"

            print("Waiting for Vue app to mount...")
            page.wait_for_selector("#main", timeout=5000)

            print("Checking for username display...")
            page.wait_for_selector("text=Hello, testuser", timeout=5000)

            print("Checking for status indicator...")
            page.wait_for_selector(".circle", timeout=5000)

            print("✅ Basic page load test passed!")
            return True

        except PlaywrightTimeout as e:
            print(f"❌ Timeout error: {e}")
            # Take screenshot on failure
            page.screenshot(path="/tmp/playwright_error.png")
            print("Screenshot saved to /tmp/playwright_error.png")
            return False
        except AssertionError as e:
            print(f"❌ Assertion failed: {e}")
            return False
        finally:
            browser.close()


def test_advanced_controls():
    """Test that advanced controls render with status filters."""
    with sync_playwright() as p:
        print("\nLaunching browser for advanced controls test...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Enable console logging
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))

        try:
            print("Navigating to main page...")
            page.goto("http://localhost?assumedid=testuser", wait_until="networkidle")

            print("Waiting for settings component to render...")
            # Wait for the advanced controls button
            page.wait_for_selector("button:has-text('Show advanced controls')", timeout=10000)

            print("Clicking 'Show advanced controls'...")
            page.click("button:has-text('Show advanced controls')")

            print("Checking for status filters...")
            page.wait_for_selector("text=Show puzzles:", timeout=5000)

            # Check that status filter checkboxes exist
            filters = page.locator(".filter").count()
            print(f"Found {filters} status filters")

            if filters == 0:
                print("❌ No status filters found!")
                page.screenshot(path="/tmp/playwright_no_filters.png")
                print("Screenshot saved to /tmp/playwright_no_filters.png")
                return False

            print("✅ Advanced controls test passed!")
            return True

        except PlaywrightTimeout as e:
            print(f"❌ Timeout error: {e}")
            page.screenshot(path="/tmp/playwright_controls_error.png")
            print("Screenshot saved to /tmp/playwright_controls_error.png")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
        finally:
            browser.close()


def test_puzzle_creation_flow():
    """Test the stepwise puzzle creation UI flow."""
    with sync_playwright() as p:
        print("\nLaunching browser for puzzle creation test...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Enable console logging
        page.on("console", lambda msg: print(f"Browser console: {msg.text}"))

        try:
            print("Navigating to add puzzle page...")
            page.goto("http://localhost/addpuzzle.php?assumedid=testuser", wait_until="networkidle")

            print("Filling in puzzle form...")
            page.fill("input[name='name']", "Test Puzzle from Playwright")
            page.fill("input[name='puzzle_uri']", "https://example.com/test-puzzle")

            # Select first round if available
            if page.locator("select[name='round_id'] option").count() > 1:
                page.select_option("select[name='round_id']", index=1)

            print("Submitting form...")
            page.click("input[type='submit']")

            print("Waiting for progress indicators...")
            # Look for progress container
            page.wait_for_selector("#progress-container", timeout=5000)

            # Wait for completion or error
            time.sleep(3)  # Give it time to complete steps

            # Check if we got redirected or see completion
            if "puzzle.php" in page.url or page.locator("text=✅").count() >= 4:
                print("✅ Puzzle creation flow test passed!")
                return True
            else:
                print("❌ Puzzle creation did not complete as expected")
                page.screenshot(path="/tmp/playwright_creation_error.png")
                return False

        except PlaywrightTimeout as e:
            print(f"❌ Timeout error: {e}")
            page.screenshot(path="/tmp/playwright_creation_timeout.png")
            return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
        finally:
            browser.close()


if __name__ == "__main__":
    print("="*60)
    print("Puzzleboss UI Tests with Playwright")
    print("="*60)

    results = []

    # Run tests
    results.append(("Basic page load", test_basic_page_load()))
    results.append(("Advanced controls", test_advanced_controls()))
    # Uncomment to test puzzle creation (creates actual test data)
    # results.append(("Puzzle creation flow", test_puzzle_creation_flow()))

    # Print summary
    print("\n" + "="*60)
    print("Test Summary:")
    print("="*60)
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} passed")
    print("="*60)

    sys.exit(0 if passed == total else 1)
