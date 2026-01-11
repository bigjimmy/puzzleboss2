"""
Selenium automation library for Puzzleboss.
Handles Google Sheets extension enablement via browser automation.
"""

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from pblib import debug_log, configstruct

# SimpleSAMLphp login page detection
SAML_LOGIN_URL_PATTERN = "importanthuntpoll.org/saml"
SAML_LOGIN_PAGE_PATTERN = "/module.php/core/loginuserpass.php"

# Google Sheets URL pattern
SHEETS_URL_PATTERN = "docs.google.com/spreadsheets"


def get_chrome_options(headless=False):
    """Configure Chrome options for Selenium."""
    options = Options()
    
    if headless:
        options.add_argument("--headless=new")
    
    # Standard options for stability
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Use a persistent profile directory if configured
    profile_dir = configstruct.get("SELENIUM_CHROME_PROFILE")
    if profile_dir:
        options.add_argument(f"--user-data-dir={profile_dir}")
        debug_log(4, f"Using Chrome profile: {profile_dir}")
    
    return options


def create_driver(headless=False):
    """Create and return a Chrome WebDriver instance."""
    options = get_chrome_options(headless)
    
    # Check for custom chromedriver path
    chromedriver_path = configstruct.get("SELENIUM_CHROMEDRIVER_PATH")
    if chromedriver_path:
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)
    
    return driver


def is_on_saml_login_page(driver):
    """Check if the browser is on the SimpleSAMLphp login page."""
    current_url = driver.current_url
    return SAML_LOGIN_URL_PATTERN in current_url and SAML_LOGIN_PAGE_PATTERN in current_url


def is_on_google_sheets(driver):
    """Check if the browser is on a Google Sheets page."""
    return SHEETS_URL_PATTERN in driver.current_url


def handle_saml_login(driver, username, password, timeout=30):
    """
    Handle SimpleSAMLphp login if we're on the login page.
    Returns True if login was handled, False if not on login page.
    """
    if not is_on_saml_login_page(driver):
        debug_log(4, "Not on SAML login page, skipping login")
        return False
    
    debug_log(3, "Detected SimpleSAMLphp login page, authenticating...")
    
    try:
        # Wait for the username field to be present
        wait = WebDriverWait(driver, timeout)
        username_field = wait.until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        
        # Find password field and login button
        password_field = driver.find_element(By.NAME, "password")
        
        # Clear and fill the fields
        username_field.clear()
        username_field.send_keys(username)
        
        password_field.clear()
        password_field.send_keys(password)
        
        # Find and click the login button
        # SimpleSAMLphp uses a submit button, try multiple selectors
        try:
            login_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        except NoSuchElementException:
            try:
                login_button = driver.find_element(By.XPATH, "//input[@type='submit']")
            except NoSuchElementException:
                login_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
        
        login_button.click()
        debug_log(3, "Submitted SAML login credentials")
        
        # Wait for redirect away from login page
        wait.until(lambda d: not is_on_saml_login_page(d))
        debug_log(3, "SAML login successful, redirected")
        
        return True
        
    except TimeoutException:
        debug_log(1, "Timeout waiting for SAML login elements")
        raise Exception("SAML login timeout")
    except Exception as e:
        debug_log(1, f"Error during SAML login: {e}")
        raise


def navigate_to_sheet_with_auth(driver, sheet_url, timeout=60):
    """
    Navigate to a Google Sheet, handling SAML authentication if needed.
    Returns True if successfully landed on the sheet.
    """
    debug_log(4, f"Navigating to sheet: {sheet_url}")
    driver.get(sheet_url)
    
    # Wait a moment for any redirects
    time.sleep(2)
    
    # Check if we need to authenticate
    if is_on_saml_login_page(driver):
        username = configstruct.get("SELENIUM_SAML_USERNAME")
        password = configstruct.get("SELENIUM_SAML_PASSWORD")
        
        if not username or not password:
            raise Exception("SAML credentials not configured (SELENIUM_SAML_USERNAME, SELENIUM_SAML_PASSWORD)")
        
        handle_saml_login(driver, username, password)
        
        # Wait for final redirect to sheets
        time.sleep(3)
    
    # Verify we're on the sheet
    wait = WebDriverWait(driver, timeout)
    try:
        wait.until(lambda d: is_on_google_sheets(d))
        debug_log(3, "Successfully navigated to Google Sheet")
        return True
    except TimeoutException:
        debug_log(1, f"Failed to reach Google Sheet, current URL: {driver.current_url}")
        return False


def enable_sheet_extension(sheet_url, extension_name="Mystery Hunt Tools", headless=False):
    """
    Enable a Google Sheets extension on the specified sheet.
    
    Args:
        sheet_url: The Google Sheets URL
        extension_name: Name of the extension in the Extensions menu
        headless: Whether to run Chrome in headless mode
        
    Returns:
        True if extension was enabled successfully, False otherwise
    """
    driver = None
    try:
        driver = create_driver(headless=headless)
        
        # Navigate to the sheet with authentication
        if not navigate_to_sheet_with_auth(driver, sheet_url):
            return False
        
        # Wait for sheet to fully load
        debug_log(4, "Waiting for sheet to fully load...")
        time.sleep(5)
        
        wait = WebDriverWait(driver, 30)
        
        # Step 1: Click on Extensions menu in the menu bar
        debug_log(4, "Looking for Extensions menu...")
        try:
            # Google Sheets uses specific menu structure - Extensions is in the menu bar
            extensions_menu = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//div[@class='menu-button' and .//span[text()='Extensions']]"))
            )
            extensions_menu.click()
            debug_log(4, "Clicked Extensions menu")
            time.sleep(1)
        except TimeoutException:
            # Try alternative selector
            try:
                extensions_menu = driver.find_element(By.XPATH, "//span[text()='Extensions']/ancestor::div[@class='menu-button']")
                extensions_menu.click()
                debug_log(4, "Clicked Extensions menu (alt selector)")
                time.sleep(1)
            except:
                # Last resort - try clicking by text content
                extensions_menu = driver.find_element(By.XPATH, "//*[contains(text(), 'Extensions')]")
                extensions_menu.click()
                debug_log(4, "Clicked Extensions menu (text selector)")
                time.sleep(1)
        
        # Step 2: Hover/click on "Mystery Hunt Tools" to open submenu
        debug_log(4, f"Looking for '{extension_name}' in dropdown...")
        try:
            # Find the extension menu item
            extension_item = wait.until(
                EC.presence_of_element_located((By.XPATH, f"//span[contains(text(), '{extension_name}')]"))
            )
            # Use ActionChains to hover (needed for submenu)
            actions = ActionChains(driver)
            actions.move_to_element(extension_item).perform()
            debug_log(4, f"Hovering over '{extension_name}'")
            time.sleep(1)
        except TimeoutException:
            debug_log(1, f"Could not find extension '{extension_name}' in menu")
            # Close menu by pressing Escape
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            return False
        
        # Step 3: Click "Enable for this spreadsheet" in the submenu
        debug_log(4, "Looking for 'Enable for this spreadsheet' option...")
        try:
            enable_option = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Enable for this spreadsheet')]"))
            )
            enable_option.click()
            debug_log(3, "Clicked 'Enable for this spreadsheet'")
            time.sleep(2)
        except TimeoutException:
            debug_log(1, "Could not find 'Enable for this spreadsheet' option")
            # Maybe it's already enabled? Check for other indicators
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            return False
        
        # Wait for extension to initialize and possibly show a dialog/confirmation
        debug_log(4, "Waiting for extension to initialize...")
        time.sleep(5)
        
        # Check for any authorization dialogs that might pop up
        try:
            # Google may show an authorization dialog
            auth_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Continue') or contains(text(), 'Allow') or contains(text(), 'Authorize')]")
            auth_button.click()
            debug_log(3, "Clicked authorization button")
            time.sleep(3)
        except NoSuchElementException:
            debug_log(4, "No authorization dialog found (may not be needed)")
        
        debug_log(3, f"Extension '{extension_name}' enabled for {sheet_url}")
        return True
        
    except Exception as e:
        debug_log(1, f"Error enabling sheet extension: {e}")
        return False
        
    finally:
        if driver:
            driver.quit()


def test_saml_auth(sheet_url=None):
    """
    Test function to verify SAML authentication is working.
    Opens a browser, navigates to a sheet, handles auth, and reports status.
    """
    if not sheet_url:
        sheet_url = "https://docs.google.com/spreadsheets"
    
    print(f"Testing SAML auth with URL: {sheet_url}")
    
    driver = None
    try:
        driver = create_driver(headless=False)  # Use headed mode for testing
        
        success = navigate_to_sheet_with_auth(driver, sheet_url)
        
        if success:
            print("SUCCESS: Authenticated and reached Google Sheets")
            print(f"Current URL: {driver.current_url}")
            input("Press Enter to close browser...")
        else:
            print("FAILED: Could not reach Google Sheets")
            print(f"Current URL: {driver.current_url}")
            input("Press Enter to close browser...")
            
    except Exception as e:
        print(f"ERROR: {e}")
        if driver:
            print(f"Current URL: {driver.current_url}")
            input("Press Enter to close browser...")
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    # Run test when executed directly
    import sys
    
    # Initialize config
    from pblib import refresh_config
    refresh_config()
    
    if len(sys.argv) > 1:
        test_saml_auth(sys.argv[1])
    else:
        test_saml_auth()
