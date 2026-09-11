#!/usr/bin/env python
"""Test setting delivery location to US zip code without VPN."""

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
logger = logging.getLogger("delivery_location")

def test_set_delivery_location():
    """Set Amazon delivery location to US zip code."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright not installed")
        return

    screenshot_dir = os.path.join("screenshots", "delivery_location_test")
    os.makedirs(screenshot_dir, exist_ok=True)

    logger.info("=== SET DELIVERY LOCATION TEST ===")
    logger.info("(No VPN active - using raw ISP connection)\n")

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
            # Step 1: Navigate to Amazon homepage
            logger.info("=== STEP 1: NAVIGATE TO AMAZON HOMEPAGE ===\n")
            logger.info("Going to https://www.amazon.com...")
            page.goto("https://www.amazon.com", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            current_url = page.url
            logger.info("✓ Current URL: %s\n", current_url)

            # Step 2: Find and click "Deliver to" location button
            logger.info("=== STEP 2: FIND DELIVERY LOCATION BUTTON ===\n")

            location_selectors = [
                "#nav-global-location-popover-link",
                "[aria-label*='Deliver to']",
                "#glow-ingress-line1",
                ".nav-line-1-container",
                "[id*='delivery']",
            ]

            location_btn = None
            for selector in location_selectors:
                try:
                    el = page.locator(selector).first
                    if el.count() > 0 and el.is_visible(timeout=2000):
                        logger.info("✓ Found location button: %s", selector)
                        location_btn = el
                        break
                except Exception:
                    continue

            if not location_btn:
                logger.error("✗ Could not find delivery location button")
                logger.info("  Taking screenshot to inspect...")
                screenshot_path = os.path.join(screenshot_dir, "homepage.png")
                page.screenshot(path=screenshot_path, full_page=True)
                logger.info("  Screenshot: %s", screenshot_path)
                return

            # Click the location button
            logger.info("Clicking location button...\n")
            location_btn.click(timeout=10000)
            page.wait_for_timeout(2000)

            # Step 3: Find zip code input and enter 98101
            logger.info("=== STEP 3: ENTER ZIP CODE ===\n")

            zip_selectors = [
                "input[placeholder*='Enter ZIP']",
                "input[id*='zip']",
                "input[name*='zip']",
                "input[type='text']",
            ]

            zip_input = None
            for selector in zip_selectors:
                try:
                    el = page.locator(selector).first
                    if el.count() > 0 and el.is_visible(timeout=2000):
                        logger.info("✓ Found zip input: %s", selector)
                        zip_input = el
                        break
                except Exception:
                    continue

            if not zip_input:
                logger.error("✗ Could not find zip code input")
                logger.info("  Looking for any text input in the popover...")
                screenshot_path = os.path.join(screenshot_dir, "popover.png")
                page.screenshot(path=screenshot_path, full_page=True)
                logger.info("  Screenshot: %s", screenshot_path)
                return

            # Enter Seattle zip code
            logger.info("Entering zip code 98101 (Seattle)...\n")
            zip_input.fill("98101")
            page.wait_for_timeout(1000)

            # Step 4: Find and click Apply/Submit button
            logger.info("=== STEP 4: SUBMIT LOCATION ===\n")

            submit_selectors = [
                "button:has-text('Apply')",
                "input[value='Apply']",
                "button[type='submit']",
                "button:has-text('Submit')",
                "button:has-text('Confirm')",
            ]

            submit_btn = None
            for selector in submit_selectors:
                try:
                    el = page.locator(selector).first
                    if el.count() > 0 and el.is_visible(timeout=2000):
                        logger.info("✓ Found submit button: %s", selector)
                        submit_btn = el
                        break
                except Exception:
                    continue

            if not submit_btn:
                logger.warning("⚠️  Could not find submit button - trying to find any button...")
                buttons = page.locator("button").all()
                if buttons:
                    logger.info("  Found %d buttons, clicking first visible one...", len(buttons))
                    for btn in buttons[:3]:
                        try:
                            if btn.is_visible(timeout=1000):
                                btn.click(timeout=5000)
                                submit_btn = btn
                                break
                        except:
                            pass

            if submit_btn:
                logger.info("Clicking submit button...\n")
                page.wait_for_timeout(2000)

            # Step 5: Navigate to product page
            logger.info("=== STEP 5: NAVIGATE TO PRODUCT PAGE ===\n")
            asin = "B0GJTFXNRX"  # TEST-001
            product_url = f"https://www.amazon.com/dp/{asin}"
            logger.info("Navigating to: %s", product_url)
            page.goto(product_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Step 6: Check page content
            logger.info("\n=== STEP 6: CHECK PAGE CONTENT ===\n")

            page_text = page.inner_text("body")
            current_url = page.url

            # Check delivery location
            if "Deliver to" in page_text:
                logger.info("✓ 'Deliver to' text visible")

            if "Pakistan" in page_text or "PKR" in page_text:
                logger.error("✗ Still showing Pakistan content!")
            elif "United States" in page_text or "USD" in page_text or "$" in page_text:
                logger.info("✅ NOW SHOWING US CONTENT!")
            else:
                logger.info("? Cannot confirm US content (check screenshot)")

            # Check for product title
            if "AirTag" in page_text:
                logger.info("✓ Product title found")

            # Check buttons
            if page.locator("#addToCart").count() > 0:
                logger.info("✓ #addToCart button present")

            price_selectors = [".a-price .a-offscreen", "[data-a-price-whole]"]
            price_found = False
            for sel in price_selectors:
                if page.locator(sel).count() > 0:
                    try:
                        price = page.locator(sel).first.inner_text()
                        logger.info("✓ Price found: %s", price)
                        price_found = True
                        break
                    except:
                        pass

            if not price_found:
                logger.warning("✗ Price not found")

            # Step 7: Take screenshot
            logger.info("\n=== STEP 7: TAKE SCREENSHOT ===\n")
            screenshot_path = os.path.join(screenshot_dir, "product_page_after_location.png")
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info("✓ Screenshot: %s", screenshot_path)

            logger.info("\n=== TEST COMPLETE ===")

        finally:
            page.close()
            ctx.close()
            browser.close()

if __name__ == "__main__":
    test_set_delivery_location()
