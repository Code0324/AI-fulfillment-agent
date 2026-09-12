"""Standalone script to bootstrap a logged-in Amazon browser session.

This is a ONE-TIME, human-assisted bootstrap. It opens a real headed browser
and waits for a human to complete login (including any 2FA/OTP) manually.

Never stores passwords. The resulting session (cookies + local storage) is
saved to backend/credentials/amazon_buyer_session.json and loaded later by
the guest-checkout flow when Amazon surfaces a sign-in wall.

IMPORTANT SECURITY NOTES
------------------------
- This script calls input() -- it blocks the terminal until a human presses
  Enter. It is NOT safe to call this from a background job or cron.
- The saved session file is sensitive (it contains live cookies). It must
  live under backend/credentials/ and be gitignored (already covered by the
  repo .gitignore entry for backend/credentials/).
- If the session file goes stale (Amazon signs out, cookies expire), the
  checkout flow will detect the sign-in page and report an Error with a
  message telling the operator to re-run this script.

Usage:
    cd backend
    python -m jobs.bootstrap_amazon_session

What it does:
    1. Launches a headed Chromium via Playwright.
    2. Navigates to https://www.amazon.com/ap/signin
    3. Prints instructions and waits for the operator to press Enter.
    4. Verifies the session looks logged in (Amazon homepage shows a greeting /
       account name rather than a sign-in page).
    5. If not logged in, warns and offers a retry (up to a small number).
    6. Saves storage_state to backend/credentials/amazon_buyer_session.json.
"""

from __future__ import annotations

import logging
import os
import sys
import textwrap
import traceback
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# This file lives at:
#   {repo_root}/backend/jobs/bootstrap_amazon_session.py
# So the backend/ directory is 2 levels above __file__, and the repo root is 3 levels above.
_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_FILE_DIR)
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)

if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dotenv import load_dotenv
from app.core.config import settings

load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=True)

def _resolve_repo_path(value: str | None, relative_to_repo_root: str) -> str:
    if value is None:
        return os.path.normpath(os.path.join(_REPO_ROOT, relative_to_repo_root))

    raw = os.path.expandvars(os.path.expanduser(value.strip()))
    if os.path.isabs(raw):
        return os.path.normpath(raw)

    lowered = raw.lower()
    if lowered.startswith("backend/") or lowered.startswith("backend\\"):
        return os.path.normpath(os.path.join(_REPO_ROOT, raw))

    return os.path.normpath(os.path.join(_REPO_ROOT, raw))


SESSION_FILE = _resolve_repo_path(
    getattr(settings, "AMAZON_BUYER_SESSION_PATH", None),
    "backend/credentials/amazon_buyer_session.json",
)
CREDENTIALS_DIR = os.path.dirname(SESSION_FILE)
SCREENSHOTS_DIR = os.path.normpath(os.path.join(_REPO_ROOT, "backend/screenshots"))
HOMEPAGE_URL = "https://www.amazon.com/"

# How many login attempts we allow before giving up.
MAX_LOGIN_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# Playwright dependency check
# ---------------------------------------------------------------------------


def _ensure_playwright() -> None:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "playwright is not installed. Run: pip install playwright && "
            "python -m playwright install chromium"
        ) from exc


# ---------------------------------------------------------------------------
# Session verification
# ---------------------------------------------------------------------------

_SIGNIN_PAGE_INDICATORS = [
    "sign in to your account",
    "enter your password",
    'id="ap_email"',
    'id="ap_email_login"',  # Amazon changed email field ID
    'id="ap_password"',
    "keep shopping",
]


def _is_sign_in_page(page: Any) -> bool:
    """Return True if the current page still looks like a sign-in page."""
    try:
        content = page.content().lower()
    except Exception:
        return True  # assume not logged in if we can't read the page
    return any(s in content for s in _SIGNIN_PAGE_INDICATORS)


def _page_has_account_greeting(page: Any) -> bool:
    """Return True if the page appears to show a logged-in account greeting.

    Amazon's logged-in homepage usually shows "Hello, Name" or a account
    menu with the account holder's name. We check for a few common signals.
    """
    try:
        content = page.content().lower()
    except Exception:
        return False

    greetings = [
        "hello,",
        "account",
        "your lists",
        "recommendations for you",
        'id="nav-link-accountList"',
    ]
    return any(g in content for g in greetings)


def _verify_logged_in(page: Any) -> bool:
    """Check whether the browser appears to be logged in.

    Returns True if the homepage shows a logged-in signal AND is not a
    sign-in page.
    """
    if _is_sign_in_page(page):
        return False
    return _page_has_account_greeting(page)


def _take_screenshot(page: Any, filename: str) -> None:
    """Capture a screenshot and save it to backend/screenshots/."""
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    try:
        page.screenshot(path=filepath)
        logger.info("✓ Screenshot saved: %s", filepath)
    except Exception as e:
        logger.warning("✗ Failed to take screenshot: %s", str(e))


# ---------------------------------------------------------------------------
# Main bootstrap
# ---------------------------------------------------------------------------


def run_bootstrap() -> Path:
    """Run the interactive Amazon session bootstrap.

    Returns the path to the saved storage_state file.
    """
    _ensure_playwright()

    os.makedirs(CREDENTIALS_DIR, exist_ok=True)

    from playwright.sync_api import sync_playwright

    # Launch Playwright ONCE for all retry attempts
    # This keeps the browser open across retries
    browser = None
    context = None

    try:
        with sync_playwright() as pw:
            # Launch the browser BEFORE asking user for input
            logger.info("\n" + "=" * 72)
            logger.info("LAUNCHING BROWSER")
            logger.info("=" * 72)

            try:
                browser = pw.chromium.launch(
                    headless=False,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        # Removed: --no-sandbox (Linux-only, not needed on Windows)
                        # Removed: --disable-dev-shm-usage (Linux-only, not needed on Windows)
                    ],
                    proxy=settings.proxy_config,
                )
                logger.info("✓ Browser launched successfully")
            except Exception as e:
                logger.error("\n✗ FATAL: Failed to launch browser")
                logger.error("Exception type: %s", type(e).__name__)
                logger.error("Exception message: %s", str(e))
                logger.error("\nFull traceback:")
                traceback.print_exc()
                raise

            try:
                context = browser.new_context(
                    viewport={"width": 1366, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    locale="en-US",
                    timezone_id="America/New_York",
                )
                logger.info("✓ Browser context created successfully")

                # Add event listeners to detect close/crash events
                def on_browser_disconnect():
                    print("\n!!! BROWSER DISCONNECTED !!!\n")
                    logger.error("!!! BROWSER DISCONNECTED !!!")

                def on_context_close():
                    print("\n!!! CONTEXT CLOSED !!!\n")
                    logger.error("!!! CONTEXT CLOSED !!!")

                browser.on("disconnected", on_browser_disconnect)
                context.on("close", on_context_close)
                logger.info("✓ Event listeners installed")

            except Exception as e:
                logger.error("\n✗ FATAL: Failed to create browser context")
                logger.error("Exception type: %s", type(e).__name__)
                logger.error("Exception message: %s", str(e))
                logger.error("\nFull traceback:")
                traceback.print_exc()
                raise

            # Create ONE page that persists across all retry attempts
            try:
                page = context.new_page()

                def on_page_close():
                    print("\n!!! PAGE CLOSED !!!\n")
                    logger.error("!!! PAGE CLOSED !!!")

                def on_page_crash():
                    print("\n!!! PAGE CRASHED !!!\n")
                    logger.error("!!! PAGE CRASHED !!!")

                page.on("close", on_page_close)
                page.on("crash", on_page_crash)
                logger.info("✓ Page created with event listeners")

                # Navigate to Amazon homepage first
                logger.info("Navigating to Amazon homepage: %s", HOMEPAGE_URL)
                page.goto(HOMEPAGE_URL, timeout=60000, wait_until="domcontentloaded")
                logger.info("✓ Homepage loaded")

                # Wait for WAF challenge if present
                page_html = page.content()
                if "AwsWafIntegration" in page_html or "challenge" in page_html.lower():
                    logger.warning("⚠ WAF challenge page detected, waiting for it to complete...")
                    page.wait_for_timeout(5000)
                    # Wait for navigation after WAF completion
                    try:
                        page.wait_for_url("https://www.amazon.com/", timeout=15000)
                        logger.info("✓ WAF challenge completed, homepage loaded")
                    except Exception:
                        logger.warning("⚠ URL didn't match expected, but continuing...")
                    page.wait_for_timeout(3000)
                else:
                    page.wait_for_timeout(2000)

                # DEBUG: Dump the page HTML to inspect structure
                try:
                    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

                    # Get full page HTML
                    page_html = page.content()
                    nav_dump_path = os.path.join(SCREENSHOTS_DIR, "nav-bar-html.txt")
                    with open(nav_dump_path, "w", encoding="utf-8") as f:
                        f.write(page_html)
                    logger.info("✓ Full page HTML dumped to: %s", nav_dump_path)
                    logger.info("File size: %d bytes", len(page_html))

                    # Also check if this is still a WAF page
                    if "challenge-container" in page_html or "AwsWafIntegration" in page_html:
                        logger.error("✗ Still on WAF challenge page after waiting!")
                except Exception as e:
                    logger.warning("✗ Could not dump HTML: %s", str(e))

                # Find and click the Sign In button/link
                # The account menu has a button to expand the dropdown
                logger.info("Looking for Account menu to expand dropdown...")
                try:
                    # Find the expand button (arrow) next to Account & Lists
                    expand_button = page.locator("#nav-link-accountList .nav-flyout-button")

                    if not expand_button.is_visible():
                        raise Exception("#nav-link-accountList expand button not visible")

                    # Click the expand button to open the dropdown
                    expand_button.click()
                    logger.info("✓ Clicked account menu expand button")
                    page.wait_for_timeout(1500)

                    # Find the "Sign in" button inside the dropdown
                    # Primary: Try class-based selector "nav-action-signin-button"
                    sign_in_button = None
                    try:
                        btn = page.locator(".nav-action-signin-button")
                        if btn.is_visible():
                            sign_in_button = btn
                            logger.info("✓ Found Sign In button by class selector (.nav-action-signin-button)")
                    except Exception:
                        pass

                    # Fallback 1: Try text-based locator for "Sign in"
                    if not sign_in_button or not sign_in_button.is_visible():
                        logger.warning("Class selector not found, trying text-based locator...")
                        try:
                            text_btn = page.get_by_text("Sign in", exact=False).first
                            if text_btn.is_visible():
                                sign_in_button = text_btn
                                logger.info("✓ Found Sign In button by text locator (get_by_text)")
                        except Exception as e:
                            logger.warning("Text locator failed: %s", str(e))

                    if not sign_in_button or not sign_in_button.is_visible():
                        raise Exception("Could not find visible Sign In button with any selector")

                    # Click the sign in button
                    sign_in_button.click()
                    logger.info("✓ Clicked Sign In button")
                    page.wait_for_timeout(2000)

                except Exception as e:
                    logger.error("✗ FATAL: Failed to click Sign In button")
                    logger.error("Exception: %s", str(e))
                    _take_screenshot(page, "bootstrap_signin_click_failed.png")
                    logger.error("Screenshot saved to bootstrap_signin_click_failed.png for debugging")
                    raise

                # Wait for the email input field to be visible (indicates real signin form)
                logger.info("Waiting for signin form email field...")
                current_url = page.url
                logger.info("Current URL after clicking Sign In: %s", current_url)

                # DEBUG: Dump signin page HTML to inspect form structure
                try:
                    page.wait_for_timeout(3000)  # Extra wait for dynamic content
                    signin_html = page.content()
                    signin_dump_path = os.path.join(SCREENSHOTS_DIR, "signin-page-html.txt")
                    with open(signin_dump_path, "w", encoding="utf-8") as f:
                        f.write(signin_html)
                    logger.info("✓ Signin page HTML dumped to: %s", signin_dump_path)
                    logger.info("File size: %d bytes", len(signin_html))
                except Exception as e:
                    logger.warning("✗ Could not dump signin HTML: %s", str(e))

                try:
                    # Try new field ID first (ap_email_login), then fallback to old (ap_email)
                    email_field = None
                    for email_id in ["ap_email_login", "ap_email"]:
                        try:
                            field = page.locator(f"#{email_id}")
                            if field.is_visible(timeout=3000):
                                email_field = field
                                logger.info("✓ Found email field with ID: #%s", email_id)
                                break
                        except Exception:
                            pass

                    if not email_field:
                        # Fallback: look for any input with type="email"
                        email_field = page.locator('input[type="email"]').first
                        if not email_field.is_visible(timeout=3000):
                            raise Exception("Could not find email field with any selector")
                        logger.info("✓ Found email field using type selector")

                    logger.info("✓ Email field visible - real signin form loaded")
                except Exception as e:
                    logger.error("✗ Email field did not appear - may have landed on wrong page")
                    logger.error("Exception: %s", str(e))
                    logger.warning("Continuing anyway - may already be on signin page...")
                    _take_screenshot(page, "bootstrap_signin_form_not_found.png")
                    # Don't raise here - user might already be on the signin page
                    # Just continue with manual input
                    page.wait_for_timeout(1000)

                # Take initial screenshot before any attempts
                logger.info("Taking initial screenshot of signin form...")
                _take_screenshot(page, "bootstrap_initial.png")

            except Exception as e:
                logger.error("\n✗ FATAL: Failed to create page or navigate to signin")
                logger.error("Exception type: %s", type(e).__name__)
                logger.error("Exception message: %s", str(e))
                logger.error("\nFull traceback:")
                traceback.print_exc()
                raise

            # NOW the browser is open with the signin page ready - enter the retry loop
            attempt = 0
            while attempt < MAX_LOGIN_ATTEMPTS:
                attempt += 1

                logger.info("")
                logger.info("=" * 72)
                logger.info("ATTEMPT %d of %d", attempt, MAX_LOGIN_ATTEMPTS)
                logger.info("=" * 72)

                if attempt == 1:
                    logger.info(
                        textwrap.dedent(
                            f"""
                            The browser is OPEN. Amazon's sign-in page should be visible.

                            INSTRUCTIONS:
                            1. Log in with your email + password
                            2. Complete 2FA/OTP if Amazon prompts for it
                            3. Wait for redirect to the Amazon homepage
                            4. When you're logged in and on the homepage, return to this terminal
                            5. Press Enter below to verify login

                            DO NOT:
                            - Close the browser window
                            - Log out
                            - Clear cookies or site data
                            """
                        ).strip()
                    )
                else:
                    logger.warning(
                        textwrap.dedent(
                            f"""
                            Previous attempt did not detect a logged-in session.
                            The browser is still open showing the current page.

                            Next steps:
                            - If you're still on a sign-in or 2FA page: complete login now
                            - If you're on the homepage: you're good
                            - Use the browser's back button if needed

                            Once ready, return here and press Enter to verify again.
                            """
                        ).strip()
                    )

                # ✓ NOW wait for user to complete login while browser is OPEN
                # Log page count and state
                open_pages = len(context.pages)
                logger.info("\n[DEBUG] Open pages in context: %d", open_pages)
                if open_pages > 0:
                    logger.info("[DEBUG] Current page URL: %s", page.url)

                # Take screenshot before waiting
                logger.info("Taking screenshot before attempt %d...", attempt)
                _take_screenshot(page, f"bootstrap_attempt_{attempt}.png")

                # DEBUG: Check page state for signin
                try:
                    email_value = page.input_value("#ap_email_login", timeout=2000)
                    logger.info("[DEBUG] Email field value: %s", "***FILLED***" if email_value else "EMPTY")
                except Exception:
                    logger.info("[DEBUG] Could not read email field")

                try:
                    continue_btn = page.locator("#continue")
                    is_enabled = continue_btn.is_enabled(timeout=1000)
                    logger.info("[DEBUG] Continue button enabled: %s", is_enabled)
                except Exception as e:
                    logger.warning("[DEBUG] Could not check Continue button: %s", str(e))

                # Try to get input from user (works in interactive terminals)
                # If no stdin available, just wait for auto-detection
                try:
                    input(f"\n[Attempt {attempt}/{MAX_LOGIN_ATTEMPTS}] Instructions:\n"
                          "1. FILL EMAIL/PHONE field with your Amazon email or phone\n"
                          "2. Click CONTINUE button\n"
                          "3. FILL PASSWORD field\n"
                          "4. Complete 2FA/OTP if prompted\n"
                          "5. When on homepage, press Enter here...\n")
                except EOFError:
                    # Non-interactive mode: wait longer and auto-detect login
                    logger.info("\n[Attempt %d/%d] Running in non-interactive mode - auto-detecting login...", attempt, MAX_LOGIN_ATTEMPTS)
                    logger.info("\nSTEPS:")
                    logger.info("1. FILL the email/phone field")
                    logger.info("2. Click the CONTINUE button")
                    logger.info("3. FILL the password field")
                    logger.info("4. Complete 2FA/OTP if prompted")
                    logger.info("5. Wait for redirect to Amazon homepage")
                    logger.info("\nWaiting up to 180 seconds for manual login completion...")

                    # Wait and check every 5 seconds if page has returned to homepage
                    for wait_count in range(36):  # 180 seconds / 5 seconds = 36 checks
                        page.wait_for_timeout(5000)
                        current_url = page.url

                        if "signin" not in current_url.lower():
                            logger.info("✓ Detected navigation away from signin page!")
                            logger.info("Current URL: %s", current_url)
                            break

                        remaining = 180 - (wait_count * 5)
                        if remaining % 30 == 0:
                            logger.info("Still waiting... %d seconds remaining", remaining)

                    logger.info("Auto-detection phase complete")

                try:
                    # Navigate to Amazon homepage to verify login and let it settle.
                    logger.info("\nNavigating to Amazon homepage: %s", HOMEPAGE_URL)
                    page.goto(HOMEPAGE_URL, timeout=60000, wait_until="domcontentloaded")
                    page.wait_for_timeout(6000)

                    # Log the current page state for debugging
                    current_url = page.url
                    page_text = "(unable to read)"
                    try:
                        page_text = page.inner_text("body")[:500]
                    except Exception as e:
                        logger.warning("Could not read page text: %s", type(e).__name__)

                    logger.info("\n" + "=" * 72)
                    logger.info("VERIFICATION CHECK")
                    logger.info("=" * 72)
                    logger.info("Current URL: %s", current_url)
                    logger.info("Page content (first 500 chars):")
                    logger.info(page_text)
                    logger.info("=" * 72)

                    logger.info("\nVerifying session looks logged in...")
                    if _verify_logged_in(page):
                        logger.info("✓ Session looks logged in!")
                    else:
                        logger.warning(
                            "✗ Could not detect logged-in session.\n"
                            "  Possible reasons:\n"
                            "  - Sign-in page is still showing\n"
                            "  - 2FA prompt is still active\n"
                            "  - Page is stuck on an intermediate prompt\n"
                            "  - Browser back-button may be needed\n\n"
                            "Attempt %d of %d will try again...",
                            attempt, MAX_LOGIN_ATTEMPTS
                        )
                        continue

                    # Give one more moment for any final redirects to settle.
                    page.wait_for_timeout(2000)

                    # Save the session.
                    logger.info("Saving session to %s", SESSION_FILE)
                    context.storage_state(path=SESSION_FILE)
                    logger.info("Session saved successfully.")
                    logger.info(
                        "The checkout automation will now load this session "
                        "whenever Amazon surfaces a sign-in wall."
                    )
                    return Path(SESSION_FILE)

                except Exception as e:
                    # Don't close page here - we're using it for next retry attempt
                    logger.error("\n✗ ERROR during verification (attempt %d):", attempt)
                    logger.error("Exception type: %s", type(e).__name__)
                    logger.error("Exception message: %s", str(e))
                    logger.error("\nFull traceback:")
                    traceback.print_exc()
                    logger.warning("Will retry with same page...")
                    continue

            # If we get here, all attempts failed.
            logger.error(
                "\n" + "=" * 72
            )
            logger.error(
                "Could not bootstrap a logged-in Amazon session after %d attempt(s).",
                MAX_LOGIN_ATTEMPTS,
            )
            logger.error(
                "Do not run the checkout automation yet -- it will fail with an "
                "'Amazon session expired or missing' error until you successfully "
                "run this script."
            )
            logger.error("=" * 72)
            sys.exit(1)

    except Exception as e:
        logger.error("\n✗ FATAL ERROR (outer scope):")
        logger.error("Exception type: %s", type(e).__name__)
        logger.error("Exception message: %s", str(e))
        logger.error("\nFull traceback:")
        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    print()
    print("=" * 72)
    print("AMAZON BUYER SESSION BOOTSTRAP")
    print("=" * 72)
    print()
    print(
        "This script opens a REAL browser window and waits for YOU to log in "
        "to Amazon manually."
    )
    print("No password is stored anywhere. Only the resulting browser session")
    print("(cookies + local storage) is saved to disk.")
    print()
    print(f"Session will be saved to: {SESSION_FILE}")
    print()
    print("If you already have a valid session file there and just want to")
    print("renew it, this script overwrites it with a fresh one.")
    print()
    print("=" * 72)
    print()

    path = run_bootstrap()
    print()
    print("Bootstrap complete.")
    print(f"Session saved to: {path}")
    print()
    print("Next step: re-run the checkout demo:")
    print("    cd backend")
    print("    python -m jobs.demo_guest_checkout_fulfillment")
    print()


if __name__ == "__main__":
    main()
