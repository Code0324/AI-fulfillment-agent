"""Quick verification that IPRoyal proxy is working and shows US IP."""

from __future__ import annotations

import json
import logging
import os
import sys

# Path setup
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from dotenv import load_dotenv

_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=True)

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

def verify_proxy():
    """Launch browser through proxy and check ipinfo.io."""
    logger.info("=" * 72)
    logger.info("PROXY VERIFICATION TEST")
    logger.info("=" * 72)

    # Check if proxy is configured
    if not settings.proxy_config:
        logger.error("✗ PROXY NOT CONFIGURED")
        logger.error("  PROXY_SERVER: %s", settings.PROXY_SERVER or "(empty)")
        logger.error("  PROXY_USERNAME: %s", settings.PROXY_USERNAME or "(empty)")
        logger.error("  PROXY_PASSWORD: %s", "***" if settings.PROXY_PASSWORD else "(empty)")
        return False

    logger.info("✓ Proxy configured:")
    logger.info("  Server: %s", settings.PROXY_SERVER)
    logger.info("  Username: %s", settings.PROXY_USERNAME)

    try:
        from playwright.sync_api import sync_playwright

        logger.info("\nLaunching browser through proxy...")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
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

                    logger.info("Navigating to https://ipinfo.io/json ...")
                    page.goto("https://ipinfo.io/json", timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)

                    # Extract JSON from page
                    content = page.content()

                    # Find the JSON in the page
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    json_str = content[start:end]

                    data = json.loads(json_str)

                    logger.info("\n" + "=" * 72)
                    logger.info("IP INFO RESPONSE:")
                    logger.info("=" * 72)
                    logger.info("IP: %s", data.get("ip"))
                    logger.info("Country: %s", data.get("country"))
                    logger.info("Region: %s", data.get("region"))
                    logger.info("City: %s", data.get("city"))
                    logger.info("Organization: %s", data.get("org"))
                    logger.info("Timezone: %s", data.get("timezone"))

                    country = data.get("country", "").upper()
                    if country == "US":
                        logger.info("\n" + "=" * 72)
                        logger.info("✓ SUCCESS: IP is US-based!")
                        logger.info("=" * 72)
                        logger.info("Proxy is working correctly. You can now proceed to bootstrap_amazon_session.py")
                        return True
                    else:
                        logger.error("\n" + "=" * 72)
                        logger.error("✗ FAILURE: IP is not in US (country: %s)", country)
                        logger.error("=" * 72)
                        logger.error("Proxy may not be working. Check credentials and proxy server.")
                        return False

                finally:
                    page.close()
                    context.close()
            finally:
                browser.close()

    except Exception as e:
        logger.error("\n" + "=" * 72)
        logger.error("✗ ERROR: Failed to verify proxy")
        logger.error("=" * 72)
        logger.error("Exception: %s", e, exc_info=True)
        return False

if __name__ == "__main__":
    success = verify_proxy()
    sys.exit(0 if success else 1)
