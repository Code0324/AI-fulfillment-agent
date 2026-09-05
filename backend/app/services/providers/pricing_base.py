"""Pricing provider abstraction.

Amazon price/inventory/product-detail lookups, kept separate from
providers/base.py's order-provider contract (BaseProvider) because pricing
is a different capability with a different selection model: exactly ONE
pricing provider is active at a time, chosen globally via the
PRICING_PROVIDER env var (see providers/registry.py), rather than several
order providers coexisting and being picked per order.source.

Every method here must do exactly one of two things: return real data from
a real source, or raise PricingProviderError (see subclasses below). Never
fabricate a price, stock status, or product title — a caller (in
particular services/fulfillment/workflow.py's price safety-gate step) must
be able to tell "checked, and here is the real number" apart from "could
not check" with certainty, because the fulfillment workflow's hard safety
rule is: if this can't be determined, STOP and route to human review.
"""

import abc
import logging

from app.services.providers.base import ProviderError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class PricingProviderError(ProviderError):
    """Base error for pricing provider failures."""


class PricingProviderNotConfiguredError(PricingProviderError):
    """The selected pricing provider has no usable credentials/config."""

    def __init__(self, provider_name: str = "unknown"):
        super().__init__(
            f"Pricing provider '{provider_name}' is not configured", recoverable=False
        )


class PricingProviderRequestError(PricingProviderError):
    """A request to the pricing provider's real data source failed
    (network error, API error, parse error, ASIN not found, etc.)."""

    def __init__(self, message: str, recoverable: bool = True):
        super().__init__(message, recoverable=recoverable)


# ---------------------------------------------------------------------------
# Base pricing provider
# ---------------------------------------------------------------------------

class PricingProviderBase(abc.ABC):
    """Abstract base class for Amazon pricing/inventory/product-detail
    providers. Every concrete implementation is synchronous, matching the
    rest of this codebase's provider methods (AmazonOrderProvider,
    TikTokOrderProvider) — services/fulfillment/workflow.py is fully
    synchronous and calls into providers directly, with no event loop of
    its own."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Whether this provider has what it needs to make a real request.
        Checked before every call; callers must not call get_price/etc. on
        an unconfigured provider and treat an exception as anything other
        than "could not check"."""
        ...

    @abc.abstractmethod
    def get_price(self, asin: str) -> dict:
        """Return {"asin", "price", "currency", "checked_at", "source"}.

        Raises PricingProviderNotConfiguredError if not configured, or
        PricingProviderRequestError if the real request fails for any
        reason (including "ASIN not found"). Never returns a fabricated or
        cached-stale-without-marking-it price.
        """
        ...

    @abc.abstractmethod
    def get_inventory_status(self, asin: str) -> dict:
        """Return {"asin", "in_stock", "available_quantity" (may be None —
        Amazon rarely exposes exact competitor/seller stock counts),
        "checked_at", "source"}.

        Raises the same errors as get_price.
        """
        ...

    @abc.abstractmethod
    def get_product_details(self, asin: str) -> dict:
        """Return {"asin", "title", "checked_at", "source", ...}.

        Raises the same errors as get_price.
        """
        ...
