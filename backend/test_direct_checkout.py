#!/usr/bin/env python
"""Test direct checkout navigation without cart."""

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
logger = logging.getLogger("direct_checkout")

def test_direct_checkout():
    """Test navigating directly to checkout URLs."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright not installed")
        return

    asin = "B0GJTXVN9Z"
    qty = 1
    screenshot_dir = os.path.join("screenshots", f"direct_checkout_{asin}")
    os.makedirs(screenshot_dir, exist_ok=True)

    logger.info("=== DIRECT CHECKOUT TEST ===")
    logger.info("ASIN: %s, Qty: %d", asin, qty)

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
            # Test different direct checkout URLs
            checkout_urls = [
                f"https://www.amazon.com/gp/buy/spc/handlers/display.html?asin={asin}&quantity={qty}",
                f"https://www.amazon.com/gp/product/{asin}/ref=ox_sc_act_title_1",
                f"https://www.amazon.com/gp/checkout/retail?asin.0={asin}&quantity.0={qty}",
                "https://www.amazon.com/gp/checkout/express.html",
                "https://www.amazon.com/gp/buy/checkoutmode=alipay",
            ]

            for i, checkout_url in enumerate(checkout_urls):
                logger.info("\n=== ATTEMPT %d ===", i + 1)
                logger.info("Testing: %s", checkout_url)

                try:
                    page.goto(checkout_url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)

                    current_url = page.url
                    logger.info("✓ Loaded, current URL: %s", current_url)

                    # Check if we're on checkout/shipping page
                    is_checkout = any(x in current_url.lower() for x in [
                        "/gp/buy",
                        "/gp/checkout",
                        "/shipping",
                        "/address",
                        "checkoutmode",
                        "cart"
                    ])

                    if is_checkout or "shipping" in page.content().lower() or "address" in page.content().lower():
                        logger.info("✅ CHECKOUT PAGE DETECTED!")
                        logger.info("   Taking screenshot...")
                        screenshot_path = os.path.join(screenshot_dir, f"checkout_attempt_{i}.png")
                        page.screenshot(path=screenshot_path, full_page=True)
                        logger.info("   Screenshot: %s", screenshot_path)

                        # Check for sign-in wall
                        html = page.content().lower()
                        if 'sign in' in html and ('password' in html or 'email' in html or 'ap_email' in html):
                            logger.warning("   ⚠️ Sign-in wall detected")
                        else:
                            logger.info("   ✓ No sign-in wall detected")

                        # List visible buttons
                        logger.info("   Looking for buttons on page...")
                        buttons = page.locator("button, input[type='submit'], input[type='button']").all()
                        logger.info("   Found %d buttons", len(buttons))
                        for j, btn in enumerate(buttons[:10]):
                            try:
                                btn_id = btn.get_attribute("id") or "(no id)"
                                btn_text = btn.inner_text() or "(no text)"
                                logger.info("     [%d] id=%s text=%s", j, btn_id, btn_text[:50])
                            except:
                                pass

                        break
                    else:
                        logger.warning("   ✗ Not a checkout page")

                except Exception as e:
                    logger.warning("   Error: %s", str(e)[:100])

            logger.info("\n=== TEST COMPLETE ===")

        finally:
            page.close()
            ctx.close()
            browser.close()

if __name__ == "__main__":
    test_direct_checkout()
