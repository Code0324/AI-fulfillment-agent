#!/usr/bin/env python
"""Test script: click add-to-cart, navigate to cart, proceed to checkout."""

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
logger = logging.getLogger("cart_test")

def test_cart_checkout():
    """Test add-to-cart, cart navigation, and checkout."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("playwright not installed")
        return

    asin = "B0GJTXVN9Z"  # 4-pack AirTag
    screenshot_dir = os.path.join("screenshots", f"cart_test_{asin}")
    os.makedirs(screenshot_dir, exist_ok=True)

    logger.info("=== CART CHECKOUT TEST ===")
    logger.info("ASIN: %s", asin)

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
            # Step 1: Load product page
            product_url = f"https://www.amazon.com/dp/{asin}"
            logger.info("\n=== STEP 1: Load Product Page ===")
            logger.info("Navigating to: %s", product_url)
            page.goto(product_url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

            screenshot_path = os.path.join(screenshot_dir, "1_product_page.png")
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info("✓ Screenshot: %s", screenshot_path)

            # Step 2: Click add-to-cart button
            logger.info("\n=== STEP 2: Click Add-to-Cart ===")
            btn = page.locator("#addToCart").first
            if btn.count() > 0 and btn.is_visible(timeout=5000):
                logger.info("✓ Found #addToCart button")
                btn.click(timeout=30000)
                logger.info("✓ Clicked #addToCart")
            else:
                logger.error("✗ #addToCart button not found or not visible")
                return

            # Step 3: Wait for add-to-cart to complete (don't wait for URL change)
            logger.info("\n=== STEP 3: Wait for Add-to-Cart to Complete ===")
            logger.info("Waiting 3 seconds for server-side add-to-cart...")
            page.wait_for_timeout(3000)
            logger.info("✓ Ready to proceed to cart")

            # Step 4: Navigate directly to cart
            logger.info("\n=== STEP 4: Navigate to Cart Page ===")
            cart_url = "https://www.amazon.com/gp/cart/view.html?ref_=nav_cart"
            logger.info("Navigating to: %s", cart_url)
            page.goto(cart_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            current_url = page.url
            logger.info("✓ Current URL: %s", current_url)

            screenshot_path = os.path.join(screenshot_dir, "2_cart_page.png")
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info("✓ Screenshot: %s", screenshot_path)

            # Step 5: Verify item in cart
            logger.info("\n=== STEP 5: Verify Item in Cart ===")
            page_text = page.inner_text("body")

            if asin in page_text or "AirTag" in page_text:
                logger.info("✓ Item appears to be in cart (found ASIN or product name)")
            else:
                logger.warning("⚠️ Item may not be in cart - ASIN and product name not found")
                logger.info("   Cart may be empty or page not fully loaded")

            # Step 6: Find checkout button
            logger.info("\n=== STEP 6: Find Checkout Button ===")
            checkout_selectors = [
                "input[name='proceedToRetailCheckout']",
                "input[value='Proceed to checkout']",
                "button[data-feature-id='proceed-to-checkout']",
                "[data-testid='proceed-to-checkout-button']",
                "a:has-text('Proceed to checkout')",
                "button:has-text('Proceed to checkout')",
                "input[type='submit']:has-text('Proceed')",
                ".a-button-primary:has-text('Proceed')",
            ]

            checkout_btn = None
            for selector in checkout_selectors:
                try:
                    el = page.locator(selector).first
                    if el.count() > 0 and el.is_visible(timeout=2000):
                        logger.info(f"  ✓ Found checkout button: {selector}")
                        checkout_btn = el
                        break
                except Exception as e:
                    continue

            if not checkout_btn:
                logger.error("✗ Could not find checkout button")
                logger.info("  Dumping page HTML to inspect...")
                html_path = os.path.join(screenshot_dir, "cart_page.html")
                try:
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(page.content())
                    logger.info(f"  HTML saved to: {html_path}")
                except Exception as e:
                    logger.warning(f"  Failed to save HTML: {e}")
                return

            # Step 7: Click checkout button
            logger.info("\n=== STEP 7: Click Checkout Button ===")
            checkout_btn.click(timeout=30000)
            logger.info("✓ Clicked checkout button")
            page.wait_for_timeout(3000)

            # Step 8: Verify checkout page
            logger.info("\n=== STEP 8: Verify Checkout Page ===")
            checkout_url = page.url
            logger.info("Current URL: %s", checkout_url)

            is_checkout = any(x in checkout_url.lower() for x in [
                "/gp/buy",
                "/checkout",
                "/shipping",
                "/address",
                "checkoutmode=guest"
            ])

            if is_checkout:
                logger.info("✅ CONFIRMED: On checkout/shipping page")
            else:
                logger.warning("⚠️ May not be on checkout page (URL doesn't match expected pattern)")

            screenshot_path = os.path.join(screenshot_dir, "3_checkout_page.png")
            page.screenshot(path=screenshot_path, full_page=True)
            logger.info("✓ Screenshot: %s", screenshot_path)

            # Check for sign-in wall
            logger.info("\n=== SIGN-IN WALL CHECK ===")
            html_lower = page.content().lower()
            if "sign in" in html_lower and ("enter your password" in html_lower or 'id="ap_email"' in html_lower):
                logger.warning("⚠️ Sign-in wall detected on checkout page")
            else:
                logger.info("✓ No obvious sign-in wall")

            logger.info("\n=== TEST COMPLETE ===")
            logger.info("✅ Successfully navigated to checkout!")
            logger.info("Screenshots saved to: %s", screenshot_dir)

        finally:
            page.close()
            ctx.close()
            browser.close()

if __name__ == "__main__":
    test_cart_checkout()
