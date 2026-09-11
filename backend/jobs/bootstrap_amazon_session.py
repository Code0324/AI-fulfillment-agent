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
SIGNIN_URL = "https://www.amazon.com/ap/signin"
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

    attempt = 0
    while attempt < MAX_LOGIN_ATTEMPTS:
        attempt += 1
        logger.info(
            textwrap.dedent(
                f"""
                ==================================================================
                AMAZON SESSION BOOTSTRAP -- ATTEMPT {attempt} of {MAX_LOGIN_ATTEMPTS}
                ==================================================================

                A headed browser will now open to:

                    {SIGNIN_URL}

                INSTRUCTIONS FOR THE OPERATOR
                ------------------------------
                1. Log in to the Amazon account you want the checkout automation
                   to use (email + password).
                2. Complete any 2FA / OTP / SMS / authenticator prompt that
                   Amazon shows.
                3. If Amazon shows any "Stay signed in?" / "Save device" / "Try
                   another way" prompts, complete them too.
                4. After login, Amazon may redirect you to the homepage or a
                   recommendations page. That is expected.
                5. Come back to this terminal and press Enter once you are
                   confident you are logged in.

                IMPORTANT:
                - Do NOT log out of the browser after this.
                - Do NOT clear cookies / site data for amazon.com.
                - The automation will reuse this session via a saved storage_state
                  file. Treat that file as sensitive.
                """
            ).strip()
        )

        input("Press Enter once you're logged in and on the Amazon homepage... ")

        with sync_playwright() as pw:
            # DEBUG: Print proxy config before launch
            logger.info("\n[DEBUG] Proxy config at runtime:")
            if settings.proxy_config:
                logger.info("  Server: %s", settings.proxy_config.get("server"))
                logger.info("  Username: %s", settings.proxy_config.get("username"))
                logger.info("  Password: %s", "***" if settings.proxy_config.get("password") else "(empty)")
            else:
                logger.error("  [ERROR] proxy_config is None or empty!")

            browser = pw.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
                proxy=settings.proxy_config,
            )
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
                try:
                    page = context.new_page()

                    # DEBUG: Verify proxy is actually working by checking ipinfo.io
                    logger.info("\n[DEBUG] Verifying proxy by checking ipinfo.io in THIS browser instance...")
                    try:
                        page.goto("https://ipinfo.io/json", timeout=30000, wait_until="domcontentloaded")
                        page.wait_for_timeout(2000)
                        import json as json_module
                        content = page.content()
                        start = content.find("{")
                        end = content.rfind("}") + 1
                        if start >= 0 and end > start:
                            json_str = content[start:end]
                            ipinfo_data = json_module.loads(json_str)
                            logger.info("[DEBUG] ipinfo.io response:")
                            logger.info("  IP: %s", ipinfo_data.get("ip"))
                            logger.info("  Country: %s", ipinfo_data.get("country"))
                            logger.info("  City: %s", ipinfo_data.get("city"))
                            logger.info("  Region: %s", ipinfo_data.get("region"))
                            country = ipinfo_data.get("country", "").upper()
                            if country == "US":
                                logger.info("[DEBUG] ✓ SUCCESS - Browser IS using US proxy!")
                            else:
                                logger.error("[DEBUG] ✗ FAILED - Browser is NOT using US proxy (country: %s)", country)
                        else:
                            logger.warning("[DEBUG] Could not parse JSON from ipinfo.io")
                    except Exception as e:
                        logger.warning("[DEBUG] ipinfo.io check failed: %s", e)

                    # Navigate to Amazon homepage and let it settle.
                    logger.info("\nNavigating to %s", HOMEPAGE_URL)
                    page.goto(HOMEPAGE_URL, timeout=60000, wait_until="domcontentloaded")
                    page.wait_for_timeout(6000)

                    logger.info("Verifying session looks logged in...")
                    if _verify_logged_in(page):
                        logger.info("Session looks logged in.")
                    else:
                        logger.warning(
                            "Could not confirm a logged-in session. "
                            "The page may still be on a sign-in wall or an "
                            "intermediate prompt. Let's try again."
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

                finally:
                    context.close()
            finally:
                browser.close()

    # If we get here, all attempts failed.
    logger.error(
        "Could not bootstrap a logged-in Amazon session after %d attempt(s). "
        "Do not run the checkout automation yet -- it will fail with an "
        "'Amazon session expired or missing' error until you successfully "
        "run this script.",
        MAX_LOGIN_ATTEMPTS,
    )
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
