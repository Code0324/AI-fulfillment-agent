"""
Debug script: Launch browser exactly like bootstrap_amazon_session.py does,
and check ipinfo.io to verify proxy is working. No user input needed.
"""

from __future__ import annotations

import json
import logging
import os
import sys

# Path setup (same as bootstrap_amazon_session.py)
_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = _FILE_DIR
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)

if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dotenv import load_dotenv
from app.core.config import settings

load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

def debug_proxy_bootstrap():
    """Test proxy in bootstrap_amazon_session.py browser context."""
    logger.info("=" * 72)
    logger.info("DEBUG: Bootstrap Proxy Configuration Check")
    logger.info("=" * 72)

    # Step 1: Check proxy config
    logger.info("\n[STEP 1] Checking proxy configuration...")
    if settings.proxy_config:
        logger.info("✓ Proxy is configured:")
        logger.info("  Server: %s", settings.proxy_config.get("server"))
        logger.info("  Username: %s", settings.proxy_config.get("username"))
        logger.info("  Password: %s", "***" if settings.proxy_config.get("password") else "(empty)")
    else:
        logger.error("✗ ERROR: proxy_config is None or empty!")
        logger.error("  PROXY_SERVER env var: %s", os.getenv("PROXY_SERVER") or "(not set)")
        logger.error("  PROXY_USERNAME env var: %s", os.getenv("PROXY_USERNAME") or "(not set)")
        logger.error("  PROXY_PASSWORD env var: %s", "***" if os.getenv("PROXY_PASSWORD") else "(not set)")
        return False

    # Step 2: Launch browser exactly like bootstrap_amazon_session.py
    logger.info("\n[STEP 2] Launching browser with proxy (headless=False like bootstrap)...")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=False,  # Same as bootstrap_amazon_session.py
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

                    # Step 3: Check ipinfo.io in this browser instance
                    logger.info("\n[STEP 3] Checking ipinfo.io in this browser instance...")
                    logger.info("Navigating to https://ipinfo.io/json ...")
                    page.goto("https://ipinfo.io/json", timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)

                    content = page.content()
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    if start >= 0 and end > start:
                        json_str = content[start:end]
                        ipinfo_data = json.loads(json_str)

                        logger.info("\n" + "=" * 72)
                        logger.info("IP INFO RESPONSE (from proxy-launched browser):")
                        logger.info("=" * 72)
                        logger.info("IP: %s", ipinfo_data.get("ip"))
                        logger.info("Country: %s", ipinfo_data.get("country"))
                        logger.info("City: %s", ipinfo_data.get("city"))
                        logger.info("Region: %s", ipinfo_data.get("region"))
                        logger.info("Organization: %s", ipinfo_data.get("org"))
                        logger.info("Timezone: %s", ipinfo_data.get("timezone"))

                        country = ipinfo_data.get("country", "").upper()
                        if country == "US":
                            logger.info("\n" + "=" * 72)
                            logger.info("✓ SUCCESS: Browser is using US proxy!")
                            logger.info("=" * 72)
                            logger.info("The proxy is working correctly in bootstrap_amazon_session.py")
                            logger.info("You can now run: python -m jobs.bootstrap_amazon_session")
                            return True
                        else:
                            logger.error("\n" + "=" * 72)
                            logger.error("✗ FAILURE: Browser is NOT using US proxy!")
                            logger.error("=" * 72)
                            logger.error("Country detected: %s", country)
                            logger.error("This means the proxy is not being applied correctly.")
                            return False
                    else:
                        logger.error("Could not parse JSON from ipinfo.io response")
                        return False

                finally:
                    page.close()
                    context.close()
            finally:
                browser.close()

    except Exception as e:
        logger.error("✗ ERROR during browser launch/check: %s", e, exc_info=True)
        return False

if __name__ == "__main__":
    success = debug_proxy_bootstrap()
    sys.exit(0 if success else 1)
