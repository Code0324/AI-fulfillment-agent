#!/usr/bin/env python
"""Check IP geolocation and detect country-switch banner on Amazon."""

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
logger = logging.getLogger("ip_banner_check")

def check_ip_and_banner():
    """Check IP location and look for Amazon country-switch banner."""
    try:
        from playwright.sync_api import sync_playwright
        import json
    except ImportError as e:
        logger.error("Import error: %s", e)
        return

    screenshot_dir = os.path.join("screenshots", "ip_and_banner_check")
    os.makedirs(screenshot_dir, exist_ok=True)

    logger.info("=== IP AND BANNER CHECK ===\n")

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
            # Step 1: Check IP geolocation
            logger.info("=== STEP 1: CHECK IP GEOLOCATION ===\n")
            logger.info("Navigating to https://ipinfo.io/json...")
            page.goto("https://ipinfo.io/json", timeout=30000)
            page.wait_for_timeout(2000)

            # Get the JSON response
            try:
                ip_data_text = page.inner_text("body")
                ip_data = json.loads(ip_data_text)

                country = ip_data.get("country", "Unknown")
                city = ip_data.get("city", "Unknown")
                ip = ip_data.get("ip", "Unknown")

                logger.info("✓ IP Information:")
                logger.info("  Country: %s", country)
                logger.info("  City: %s", city)
                logger.info("  IP: %s", ip)

                if country == "US":
                    logger.info("  ✅ IP IS IN UNITED STATES")
                elif country == "PK":
                    logger.error("  ❌ IP IS IN PAKISTAN")
                else:
                    logger.warning("  ⚠️  IP IS IN: %s (not US or PK)", country)

            except Exception as e:
                logger.error("Error parsing IP info: %s", e)

            # Step 2: Navigate to Amazon product page
            logger.info("\n=== STEP 2: NAVIGATE TO AMAZON PRODUCT PAGE ===\n")
            asin = "B0GJTXVN9Z"
            product_url = f"https://www.amazon.com/dp/{asin}"
            logger.info("Navigating to: %s", product_url)

            page.goto(product_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            current_url = page.url
            logger.info("✓ Current URL: %s", current_url)

            # Step 3: Look for country-switch banner
            logger.info("\n=== STEP 3: CHECK FOR COUNTRY-SWITCH BANNER ===\n")

            page_html = page.content()
            page_text = page.inner_text("body")

            # Search for common Amazon banner patterns
            banner_patterns = [
                "pakistan",
                "country",
                "visiting from",
                "continue shopping",
                "switch to",
                "amazon.pk",
                "deliver to",
                "change your delivery",
            ]

            found_patterns = []
            for pattern in banner_patterns:
                if pattern in page_html.lower():
                    found_patterns.append(pattern)

            if found_patterns:
                logger.info("⚠️  Found potential banner keywords:")
                for pattern in found_patterns:
                    logger.info("  - '%s'", pattern)
            else:
                logger.info("✓ No obvious banner keywords found")

            # Look for visible dialogs/modals
            logger.info("\n=== STEP 4: CHECK FOR VISIBLE DIALOGS ===\n")

            dialogs = page.locator("[role='dialog'], .modal, .popup, [id*='dialog'], [id*='modal'], [id*='popup']").all()
            logger.info("Found %d potential dialog elements", len(dialogs))

            for i, dialog in enumerate(dialogs[:5]):
                try:
                    if dialog.is_visible(timeout=1000):
                        dialog_text = dialog.inner_text()
                        logger.info("\n  Dialog %d (visible):", i)
                        logger.info("    Text: %s", dialog_text[:200])
                except Exception:
                    pass

            # Check for specific Amazon banner divs
            banner_selectors = [
                "[class*='banner']",
                "[class*='dialog']",
                "[id*='banner']",
                "[id*='alert']",
                ".a-alert",
            ]

            logger.info("\n=== STEP 5: CHECK SPECIFIC AMAZON BANNERS ===\n")

            for selector in banner_selectors:
                try:
                    elements = page.locator(selector).all()
                    if elements:
                        logger.info("Found %d element(s) matching '%s'", len(elements), selector)
                        for el in elements[:2]:
                            try:
                                if el.is_visible(timeout=500):
                                    text = el.inner_text()
                                    logger.info("  Text: %s", text[:150])
                            except:
                                pass
                except Exception:
                    pass

            # Take screenshot
            logger.info("\n=== STEP 6: SCREENSHOT ===\n")
            screenshot_path = os.path.join(screenshot_dir, "amazon_product_page.png")
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info("✓ Screenshot saved: %s", screenshot_path)

            # Check if we can find the buy button
            logger.info("\n=== STEP 7: CHECK FOR BUY BUTTONS ===\n")

            if page.locator("#addToCart").count() > 0:
                logger.info("✓ #addToCart button found")
            else:
                logger.info("✗ #addToCart button NOT found")

            if page.locator("#buy-now-button").count() > 0:
                logger.info("✓ #buy-now-button button found")
            else:
                logger.info("✗ #buy-now-button button NOT found")

            # Check if "Deliver to Pakistan" banner is visible
            if "Deliver to Pakistan" in page.inner_text("body"):
                logger.warning("⚠️  'Deliver to Pakistan' text found on page")
            else:
                logger.info("✓ 'Deliver to Pakistan' text NOT found")

            logger.info("\n=== CHECK COMPLETE ===")

        finally:
            page.close()
            ctx.close()
            browser.close()

if __name__ == "__main__":
    check_ip_and_banner()
