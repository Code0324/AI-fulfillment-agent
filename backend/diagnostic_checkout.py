#!/usr/bin/env python
"""Diagnostic script: load Amazon product page in headed mode and capture HTML/screenshot."""

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
)

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("diagnostic")

def run_diagnostic(asin: str) -> None:
    """Load a product page in headed mode and capture diagnostics."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright not installed")
        return

    logger.info("=== DIAGNOSTIC: Loading Amazon product page in HEADED mode ===")
    logger.info("ASIN: %s", asin)
    logger.info("URL: %s", AMAZON_DP_URL.format(asin=asin))

    order_dir = os.path.join(CHECKOUT_SCREENSHOT_DIR, f"diagnostic_{asin}")
    os.makedirs(order_dir, exist_ok=True)

    with sync_playwright() as pw:
        # HEADED MODE (not headless) so we can see what's happening
        browser = pw.chromium.launch(
            headless=False,  # <-- HEADED MODE
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
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

            # Wait for page to stabilize
            logger.info("Waiting 5 seconds for page to stabilize...")
            page.wait_for_timeout(5000)

            # Get current URL (to detect redirects)
            current_url = page.url
            logger.info("Current URL: %s", current_url)

            # Take screenshot
            screenshot_path = os.path.join(order_dir, "product_page.png")
            logger.info("Taking screenshot: %s", screenshot_path)
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info("✓ Screenshot saved")

            # Get HTML
            html_path = os.path.join(order_dir, "product_page.html")
            html_content = page.content()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info("✓ HTML saved: %s", html_path)
            logger.info("  HTML size: %d bytes", len(html_content))

            # Check for bot-detection indicators
            logger.info("\n=== CHECKING FOR BOT-DETECTION INDICATORS ===")
            html_lower = html_content.lower()

            indicators = {
                "CAPTCHA": ["captcha", "recaptcha"],
                "Robot Check": ["robot check", "verify you are human", "verify you're human"],
                "Unusual Traffic": ["unusual traffic", "unusual activity", "suspicious activity"],
                "Sign In Wall": ["sign in to your account", "enter your password", 'id="ap_email"'],
                "Access Denied": ["access denied", "403", "blocked"],
                "Bot Detection": ["bot", "automated", "automation detected"],
            }

            found_any = False
            for category, keywords in indicators.items():
                for keyword in keywords:
                    if keyword in html_lower:
                        logger.warning("  ⚠️ FOUND: %s - '%s'", category, keyword)
                        found_any = True
                        break

            if not found_any:
                logger.info("  ✓ No obvious bot-detection indicators found in HTML")

            # Get page title
            page_title = page.title()
            logger.info("\n=== PAGE TITLE ===")
            logger.info(page_title)

            # Check for product title
            logger.info("\n=== PRODUCT TITLE DETECTION ===")
            try:
                title_el = page.locator("#productTitle").first
                if title_el.count() > 0:
                    title_text = title_el.inner_text()
                    logger.info("  ✓ Found #productTitle: %s", title_text[:100])
                else:
                    logger.warning("  ✗ #productTitle not found")
            except Exception as e:
                logger.warning("  ✗ Error checking title: %s", e)

            # Check for buy-box
            logger.info("\n=== BUY-BOX DETECTION ===")
            try:
                buy_box = page.locator("#buy-box, .buy-box, #buybox").first
                if buy_box.count() > 0:
                    logger.info("  ✓ Found buy-box element")
                    # Check for buttons inside
                    add_to_cart = buy_box.locator("#add-to-cart-button").first
                    if add_to_cart.count() > 0:
                        logger.info("    ✓ Found #add-to-cart-button inside buy-box")
                    else:
                        logger.warning("    ✗ #add-to-cart-button NOT found in buy-box")
                else:
                    logger.warning("  ✗ buy-box NOT found on page")
            except Exception as e:
                logger.warning("  ✗ Error checking buy-box: %s", e)

            # Check for price
            logger.info("\n=== PRICE DETECTION ===")
            try:
                price_el = page.locator(".a-price .a-offscreen").first
                if price_el.count() > 0:
                    price_text = price_el.inner_text()
                    logger.info("  ✓ Found price: %s", price_text)
                else:
                    logger.warning("  ✗ Price (.a-price .a-offscreen) NOT found")
            except Exception as e:
                logger.warning("  ✗ Error checking price: %s", e)

            logger.info("\n=== DIAGNOSTIC COMPLETE ===")
            logger.info("Screenshots and HTML saved to: %s", order_dir)
            logger.info("\nNEXT STEPS:")
            logger.info("1. Open the screenshot: %s", screenshot_path)
            logger.info("2. Inspect the HTML: %s", html_path)
            logger.info("3. Look for any bot-detection or access-denied pages")

        finally:
            page.close()
            ctx.close()
            browser.close()

if __name__ == "__main__":
    asin = "B0GJTXVN9Z"  # 4-pack AirTag
    run_diagnostic(asin)
