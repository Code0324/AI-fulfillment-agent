"""Amazon public-product-page scraping pricing provider — LAST RESORT ONLY.

=============================================================================
WARNING — READ BEFORE ENABLING (PRICING_PROVIDER=scrape)
=============================================================================
This provider fetches https://www.amazon.com/dp/{asin} as an anonymous HTTP
client and parses price/availability/title out of the returned HTML. It is:

  - FRAGILE: Amazon's page markup changes without notice and without
    versioning. A selector that works today can silently start returning
    nothing (or the wrong value) tomorrow — this provider raises rather
    than guessing when a selector doesn't match (see _extract_price/etc
    below), but it cannot detect "the page changed and I'm now parsing the
    wrong element" the way an API contract change would surface as an
    error code.
  - ToS-SENSITIVE: Amazon's Conditions of Use prohibit automated data
    collection/scraping of their retail site outside of licensed APIs
    (PA-API, SP-API). Running this in production is a real ToS exposure,
    not a hypothetical one — it exists here as a documented fallback for
    environments where PA-API access isn't available, not as a
    recommended default.
  - UNRELIABLE AT SCALE: no official rate limits exist to respect (unlike
    PA-API/SP-API), so this self-imposes a conservative delay between
    requests, and Amazon may still block, CAPTCHA, or serve degraded
    content to a client it detects as automated — this provider does not
    attempt to evade such detection (no proxy rotation, no CAPTCHA
    solving, no header spoofing beyond a plain, honest User-Agent).

This is READ-ONLY: it only ever performs a GET against a public product
page. It never logs in, never adds anything to a cart, never places an
order. That does not make it safe to enable by default — PRICING_PROVIDER
defaults to "mock" (see .env.example) specifically so choosing "scrape" is
a deliberate, informed decision at deploy time, not an accident.
=============================================================================
"""

import logging
import re
import time
from datetime import datetime, timezone

import httpx

from app.services.providers.pricing_base import (
    PricingProviderBase,
    PricingProviderNotConfiguredError,
    PricingProviderRequestError,
)

logger = logging.getLogger(__name__)

PRODUCT_URL_TEMPLATE = "https://www.amazon.com/dp/{asin}"

# Self-imposed minimum delay between requests — see module docstring.
# There is no official rate limit to match; this is a deliberately
# conservative floor, not a documented Amazon requirement.
MIN_REQUEST_INTERVAL_SECONDS = 3.0

# Plain, honest identification — no attempt to impersonate a browser.
USER_AGENT = "AmazonAIFulfillmentAgent-ScrapePricingProvider/0.1.0 (read-only price check)"

# Price: "$1,234.56" or "$19.99" inside the offscreen price span Amazon
# commonly uses. Deliberately narrow — a non-match raises rather than
# falling back to a looser (more fabrication-prone) pattern.
_PRICE_PATTERN = re.compile(
    r'class="a-offscreen">\s*\$([0-9][0-9,]*\.[0-9]{2})\s*<', re.IGNORECASE
)
_TITLE_PATTERN = re.compile(
    r'id="productTitle"[^>]*>\s*([^<]+?)\s*<', re.IGNORECASE
)
_AVAILABILITY_PATTERN = re.compile(
    r'id="availability"[^>]*>.*?<span[^>]*>\s*([^<]+?)\s*<', re.IGNORECASE | re.DOTALL
)


class ScrapePricingProvider(PricingProviderBase):
    """Last-resort pricing provider: parses Amazon's public product page.

    SAFETY:
    - Read-only GET requests only — never purchases, never authenticates.
    - Self-rate-limited (see MIN_REQUEST_INTERVAL_SECONDS).
    - Raises PricingProviderRequestError rather than fabricating a value
      when a selector doesn't match the fetched page.
    - is_configured is a simple opt-in flag
      (AMAZON_SCRAPE_PRICING_ENABLED) — this provider needs no
      credentials, but must still be explicitly enabled given the
      ToS/fragility caveats above; it is never active by accident.
    """

    def __init__(self, enabled: bool | None = None):
        from app.core.config import settings

        self._enabled = enabled if enabled is not None else settings.AMAZON_SCRAPE_PRICING_ENABLED
        self._last_request_time: float = 0.0

    @property
    def provider_name(self) -> str:
        return "scrape_pricing_provider"

    @property
    def is_configured(self) -> bool:
        return bool(self._enabled)

    def _require_configured(self) -> None:
        if not self.is_configured:
            raise PricingProviderNotConfiguredError(self.provider_name)

    def _enforce_rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        self._last_request_time = time.time()

    def _fetch_page(self, asin: str) -> str:
        self._require_configured()
        self._enforce_rate_limit()

        url = PRODUCT_URL_TEMPLATE.format(asin=asin)
        try:
            with httpx.Client(follow_redirects=True) as client:
                response = client.get(
                    url,
                    headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
                    timeout=30.0,
                )
        except httpx.TimeoutException as e:
            raise PricingProviderRequestError(f"Scrape request timed out for ASIN {asin}", recoverable=True) from e
        except httpx.NetworkError as e:
            raise PricingProviderRequestError(
                f"Scrape network error for ASIN {asin}: {type(e).__name__}", recoverable=True
            ) from e

        if response.status_code != 200:
            recoverable = response.status_code == 429 or response.status_code >= 500
            raise PricingProviderRequestError(
                f"Scrape request for ASIN {asin} returned HTTP {response.status_code} "
                f"(this includes anti-bot blocking/CAPTCHA pages — see module docstring)",
                recoverable=recoverable,
            )
        return response.text

    # -----------------------------------------------------------------------
    # PricingProviderBase
    # -----------------------------------------------------------------------

    def get_price(self, asin: str) -> dict:
        html = self._fetch_page(asin)
        match = _PRICE_PATTERN.search(html)
        if not match:
            raise PricingProviderRequestError(
                f"Could not find a price on the Amazon product page for ASIN {asin} — "
                f"page markup may have changed, or the item may be unavailable "
                f"(refusing to fabricate a price)",
                recoverable=False,
            )
        price = float(match.group(1).replace(",", ""))
        return {
            "asin": asin,
            "price": price,
            "currency": "USD",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": self.provider_name,
        }

    def get_inventory_status(self, asin: str) -> dict:
        html = self._fetch_page(asin)
        match = _AVAILABILITY_PATTERN.search(html)
        message = match.group(1).strip() if match else ""
        # Absence of an explicit "out of stock"/"unavailable" phrase is NOT
        # treated as proof of in-stock — an unmatched page returns
        # in_stock=None (unknown), never a guessed True.
        if not match:
            in_stock = None
        else:
            lowered = message.lower()
            in_stock = not any(phrase in lowered for phrase in ("out of stock", "unavailable", "currently unavailable"))
        return {
            "asin": asin,
            "in_stock": in_stock,
            "available_quantity": None,  # never exposed on the public page
            "availability_message": message or None,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": self.provider_name,
        }

    def get_product_details(self, asin: str) -> dict:
        html = self._fetch_page(asin)
        match = _TITLE_PATTERN.search(html)
        if not match:
            raise PricingProviderRequestError(
                f"Could not find a product title on the Amazon product page for ASIN {asin} "
                f"(refusing to fabricate one)",
                recoverable=False,
            )
        return {
            "asin": asin,
            "title": match.group(1).strip(),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": self.provider_name,
        }
