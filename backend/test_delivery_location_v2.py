#!/usr/bin/env python
"""Retry setting delivery location with more careful popover handling."""

import sys
import os
from dotenv import load_dotenv

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=True)

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("delivery_v2")

def test_delivery_v2():
    """Set delivery location with better popover handling."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright not installed")
        return

    screenshot_dir = os.path.join("screenshots", "delivery_v2")
    os.makedirs(screenshot_dir, exist_ok=True)

    logger.info("=== DELIVERY LOCATION v2 TEST ===\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
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
            # Navigate to homepage
            logger.info("Step 1: Navigate to Amazon homepage")
            page.goto("https://www.amazon.com", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            logger.info("✓ Homepage loaded\n")

            # Take initial screenshot
            screenshot_path = os.path.join(screenshot_dir, "1_homepage.png")
            page.screenshot(path=screenshot_path, full_page=True)

            # Click location button
            logger.info("Step 2: Click location button")
            location_btn = page.locator("#nav-global-location-popover-link")
            if location_btn.count() > 0:
                logger.info("✓ Found location button")
                location_btn.click(timeout=10000)
                page.wait_for_timeout(3000)
                logger.info("✓ Clicked location button\n")
            else:
                logger.error("✗ Location button not found")
                return

            # Take screenshot of popover
            screenshot_path = os.path.join(screenshot_dir, "2_popover_open.png")
            page.screenshot(path=screenshot_path, full_page=True)

            # Find all inputs and buttons in popover
            logger.info("Step 3: Inspect popover elements")
            inputs = page.locator("input[type='text']").all()
            logger.info("Found %d text inputs", len(inputs))

            # Clear any existing value and enter zip
            if inputs:
                first_input = inputs[0]
                logger.info("Clearing input and entering 98101...")
                first_input.fill("")  # Clear
                first_input.type("98101", delay=100)
                page.wait_for_timeout(1000)

                # Try pressing Enter to submit
                logger.info("Pressing Enter to submit...")
                first_input.press("Enter")
                page.wait_for_timeout(2000)
                logger.info("✓ Entered zip code and pressed Enter\n")

            # Take screenshot after entering zip
            screenshot_path = os.path.join(screenshot_dir, "3_zip_entered.png")
            page.screenshot(path=screenshot_path, full_page=True)

            logger.info("Step 4: Wait for location to update")
            page.wait_for_timeout(4000)
            logger.info("✓ Location update complete\n")

            # Take screenshot after submit
            screenshot_path = os.path.join(screenshot_dir, "4_after_submit.png")
            page.screenshot(path=screenshot_path, full_page=True)

            # Check if location changed on homepage
            logger.info("Step 5: Verify location on homepage")
            home_text = page.inner_text("body")

            if "98101" in home_text or "Seattle" in home_text or "WA" in home_text:
                logger.info("✅ Seattle location appears in page")
            elif "Pakistan" in home_text:
                logger.error("❌ Still showing Pakistan")
            else:
                logger.info("? Location unclear")

            # Now navigate to product page
            logger.info("\nStep 6: Navigate to product page")
            asin = "B0GJTFXNRX"
            product_url = f"https://www.amazon.com/dp/{asin}"
            page.goto(product_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            logger.info("✓ Product page loaded\n")

            # Check content
            logger.info("Step 7: Check product page content")
            page_text = page.inner_text("body")

            if "Pakistan" in page_text or "PKR" in page_text:
                logger.error("❌ Still showing Pakistan content")
            else:
                logger.info("✅ No Pakistan content detected!")

            if "AirTag" in page_text:
                logger.info("✓ Product found")

            # Check for US indicators
            if "USD" in page_text or "$" in page_text or "United States" in page_text:
                logger.info("✅ US pricing/content detected!")

            # Take final screenshot
            screenshot_path = os.path.join(screenshot_dir, "5_product_final.png")
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info("\n✓ Screenshot: %s", screenshot_path)

            logger.info("\n=== TEST COMPLETE ===")

        finally:
            page.close()
            ctx.close()
            browser.close()

if __name__ == "__main__":
    test_delivery_v2()
