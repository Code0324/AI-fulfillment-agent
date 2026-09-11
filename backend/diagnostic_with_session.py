#!/usr/bin/env python
"""Enhanced diagnostic: load saved session, increase wait times, check for button/price/login."""

import sys
import os
from dotenv import load_dotenv

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=True)

from app.services.fulfillment.guest_checkout import (
    CHECKOUT_SCREENSHOT_DIR,
    AMAZON_DP_URL,
    DEFAULT_TIMEOUT_MS,
    SESSION_FILE,
)

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("diagnostic_session")

def run_diagnostic_with_session(asin: str) -> None:
    """Load product page WITH saved session and increased wait time."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright not installed")
        return

    logger.info("=== ENHANCED DIAGNOSTIC: Logged-in Session + Extended Wait ===")
    logger.info("ASIN: %s", asin)
    logger.info("Session file: %s", SESSION_FILE)
    logger.info("Session file exists: %s", os.path.exists(SESSION_FILE))
    logger.info("URL: %s", AMAZON_DP_URL.format(asin=asin))

    order_dir = os.path.join(CHECKOUT_SCREENSHOT_DIR, f"diagnostic_session_{asin}")
    os.makedirs(order_dir, exist_ok=True)

    with sync_playwright() as pw:
        # HEADED MODE (not headless)
        browser = pw.chromium.launch(
            headless=False,  # <-- HEADED MODE
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        # Load session if it exists
        if os.path.exists(SESSION_FILE):
            logger.info("✓ Loading saved session from: %s", SESSION_FILE)
            ctx = browser.new_context(
                storage_state=SESSION_FILE,
                viewport={"width": 1366, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/New_York",
            )
        else:
            logger.warning("⚠️ Session file NOT FOUND - proceeding as guest")
            ctx = browser.new_context(
                viewport={"width": 1366, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/New_York",
            )

        page = ctx.new_page()

        try:
            # Navigate to product page
            product_url = AMAZON_DP_URL.format(asin=asin)
            logger.info("Navigating to: %s", product_url)
            page.goto(product_url, timeout=DEFAULT_TIMEOUT_MS, wait_until="domcontentloaded")

            # EXTENDED WAIT: 12-15 seconds for JavaScript to fully render
            logger.info("Waiting 12 seconds for JavaScript rendering (extended)...")
            page.wait_for_timeout(12000)

            # Get current URL
            current_url = page.url
            logger.info("Current URL: %s", current_url)

            # Take screenshot
            screenshot_path = os.path.join(order_dir, "product_page_session.png")
            logger.info("Taking screenshot: %s", screenshot_path)
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info("✓ Screenshot saved")

            # Get HTML
            html_path = os.path.join(order_dir, "product_page_session.html")
            html_content = page.content()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info("✓ HTML saved: %s", html_path)
            logger.info("  HTML size: %d bytes", len(html_content))

            # Check for login status
            logger.info("\n=== LOGIN STATUS CHECK ===")
            html_lower = html_content.lower()
            page_text = page.inner_text("body") if page.locator("body").count() > 0 else ""

            login_indicators = {
                "Hello": "Hello," in page_text or "hello," in page_text,
                "Account Name": "Your Account" in page_text,
                "Sign In Link": "Sign in" not in page_text or "sign in to your account" not in html_lower,
            }

            for indicator, found in login_indicators.items():
                status = "✓" if found else "✗"
                logger.info(f"  {status} {indicator}")

            # Check for bot-detection indicators
            logger.info("\n=== BOT-DETECTION CHECK ===")
            indicators = {
                "CAPTCHA": ["captcha", "recaptcha"],
                "Robot Check": ["robot check", "verify you are human"],
                "Unusual Traffic": ["unusual traffic", "suspicious activity"],
                "Amabot": ["amabot"],
                "Bot Detection": ["bot detection"],
            }

            found_any = False
            for category, keywords in indicators.items():
                for keyword in keywords:
                    if keyword in html_lower:
                        logger.warning(f"  ⚠️ FOUND: {category} - '{keyword}'")
                        found_any = True
                        break

            if not found_any:
                logger.info("  ✓ No obvious bot-detection indicators found")

            # Check for product title
            logger.info("\n=== PRODUCT TITLE ===")
            try:
                title_el = page.locator("#productTitle").first
                if title_el.count() > 0:
                    title_text = title_el.inner_text()
                    logger.info(f"  ✓ Found: {title_text[:100]}")
                else:
                    logger.warning("  ✗ #productTitle not found")
            except Exception as e:
                logger.warning(f"  ✗ Error: {e}")

            # CHECK #add-to-cart-button
            logger.info("\n=== ADD-TO-CART BUTTON CHECK ===")
            try:
                btn = page.locator("#add-to-cart-button").first
                if btn.count() > 0:
                    is_visible = btn.is_visible(timeout=1000)
                    is_enabled = btn.is_enabled(timeout=1000)
                    logger.info(f"  ✅ #add-to-cart-button FOUND!")
                    logger.info(f"     Visible: {is_visible}")
                    logger.info(f"     Enabled: {is_enabled}")
                else:
                    logger.warning("  ✗ #add-to-cart-button NOT found")
            except Exception as e:
                logger.warning(f"  ✗ Error checking button: {e}")

            # CHECK PRICE
            logger.info("\n=== PRICE CHECK ===")
            try:
                price_el = page.locator(".a-price .a-offscreen").first
                if price_el.count() > 0:
                    price_text = price_el.inner_text()
                    logger.info(f"  ✅ Price FOUND: {price_text}")
                else:
                    logger.warning("  ✗ Price (.a-price .a-offscreen) NOT found")
                    # Try alternative selector
                    price_alt = page.locator("[data-a-price-whole]").first
                    if price_alt.count() > 0:
                        logger.info(f"  (Alt selector found: {price_alt.inner_text()})")
            except Exception as e:
                logger.warning(f"  ✗ Error checking price: {e}")

            # Check buy-box
            logger.info("\n=== BUY-BOX STRUCTURE ===")
            try:
                buy_box = page.locator("#buy-box, .buy-box, #buybox").first
                if buy_box.count() > 0:
                    logger.info("  ✓ Buy-box container found")
                    # List what's inside
                    buttons = buy_box.locator("button, input[type='submit'], input[type='button']").all()
                    logger.info(f"    Buttons inside buy-box: {len(buttons)}")
                    for i, btn in enumerate(buttons[:5]):
                        try:
                            btn_id = btn.get_attribute("id") or "(no id)"
                            btn_type = btn.get_attribute("type") or "button"
                            logger.info(f"      [{i}] type={btn_type}, id={btn_id}")
                        except:
                            pass
                else:
                    logger.warning("  ✗ buy-box NOT found")
            except Exception as e:
                logger.warning(f"  ✗ Error: {e}")

            logger.info("\n=== DIAGNOSTIC COMPLETE ===")
            logger.info("Files saved to: %s", order_dir)

        finally:
            page.close()
            ctx.close()
            browser.close()

if __name__ == "__main__":
    asin = "B0GJTXVN9Z"  # 4-pack AirTag
    run_diagnostic_with_session(asin)
