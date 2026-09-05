"""Mock Pricing Provider — local deterministic pricing data.

All data is synthetic and derived deterministically from the ASIN (a stable
hash), never randomized — so the same ASIN always returns the same price
within a process, which is what makes this usable in tests that assert on
specific values. No real Amazon calls, no network requests.
"""

import hashlib
import logging
from datetime import datetime, timezone

from app.services.providers.pricing_base import PricingProviderBase

logger = logging.getLogger(__name__)

# A handful of explicit, human-readable fixtures for the ASINs this repo's
# own tests/docs reference — anything else falls back to the deterministic
# hash-derived price below, so no ASIN is ever "unknown" to the mock.
KNOWN_MOCK_PRICES: dict[str, dict] = {
    "B0MOCKASIN01": {"price": 19.99, "in_stock": True, "available_quantity": 42, "title": "Synthetic Widget Alpha"},
    "B0MOCKASIN02": {"price": 249.00, "in_stock": True, "available_quantity": 5, "title": "Synthetic Widget Beta"},
    "B0MOCKASIN03": {"price": 899.99, "in_stock": False, "available_quantity": 0, "title": "Synthetic Widget Gamma (out of stock)"},
}


def _deterministic_price(asin: str) -> float:
    """Derive a stable, plausible-looking price ($5.00–$505.00) from the
    ASIN's hash — same ASIN always yields the same price, no randomness."""
    digest = hashlib.sha256(asin.encode("utf-8")).hexdigest()
    cents = int(digest[:8], 16) % 50000
    return round(5.00 + cents / 100, 2)


class MockPricingProvider(PricingProviderBase):
    """Local mock pricing provider using deterministic synthetic data."""

    @property
    def provider_name(self) -> str:
        return "mock_pricing_provider"

    @property
    def is_configured(self) -> bool:
        # Always usable — that's the point of a mock provider.
        return True

    def _fixture(self, asin: str) -> dict:
        return KNOWN_MOCK_PRICES.get(asin) or {
            "price": _deterministic_price(asin),
            "in_stock": True,
            "available_quantity": 100,
            "title": f"Synthetic Product {asin}",
        }

    def get_price(self, asin: str) -> dict:
        logger.info("MockPricingProvider: get_price(%s)", asin)
        fixture = self._fixture(asin)
        return {
            "asin": asin,
            "price": fixture["price"],
            "currency": "USD",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": self.provider_name,
        }

    def get_inventory_status(self, asin: str) -> dict:
        logger.info("MockPricingProvider: get_inventory_status(%s)", asin)
        fixture = self._fixture(asin)
        return {
            "asin": asin,
            "in_stock": fixture["in_stock"],
            "available_quantity": fixture["available_quantity"],
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": self.provider_name,
        }

    def get_product_details(self, asin: str) -> dict:
        logger.info("MockPricingProvider: get_product_details(%s)", asin)
        fixture = self._fixture(asin)
        return {
            "asin": asin,
            "title": fixture["title"],
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "source": self.provider_name,
        }


mock_pricing_provider = MockPricingProvider()
