"""Provider registry — central registry for all providers.

Manages provider instances and ensures mock-only mode.
CHUNK 1V: Adds Amazon sandbox provider when credentials are available.
"""

import logging
from typing import Any

from app.services.providers.base import (
    BaseProvider,
    ProviderEnvironment,
    ensure_mock_mode,
)
from app.services.providers.mock.order_provider import MockOrderProvider
from app.services.providers.mock.supplier_provider import MockSupplierProvider
from app.services.providers.mock.tracking_provider import MockTrackingProvider
from app.services.providers.notifications_base import NotificationProviderBase
from app.services.providers.pricing_base import PricingProviderBase

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Central registry for all providers.

    In CHUNK 1V:
    - Mock providers are always registered
    - Amazon sandbox provider is registered when credentials are available
    """

    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}
        self._pricing_provider: PricingProviderBase | None = None
        self._notification_provider: NotificationProviderBase | None = None

    def register(self, provider: BaseProvider) -> None:
        """Register a provider."""
        name = provider.provider_name
        if name in self._providers:
            logger.warning("Overwriting provider: %s", name)
        self._providers[name] = provider
        logger.info(
            "Registered provider: %s (env=%s, mock=%s)",
            name,
            provider.environment.value,
            provider.is_mock,
        )

    def get(self, name: str) -> BaseProvider | None:
        """Get a provider by name."""
        return self._providers.get(name)

    def get_order_provider(self) -> MockOrderProvider:
        """Get the mock order provider."""
        provider = self._providers.get("mock_order_provider")
        if provider is None:
            raise RuntimeError("Order provider not registered")
        return provider  # type: ignore

    def get_supplier_provider(self) -> MockSupplierProvider:
        """Get the supplier provider."""
        provider = self._providers.get("mock_supplier_provider")
        if provider is None:
            raise RuntimeError("Supplier provider not registered")
        return provider  # type: ignore

    def get_tracking_provider(self) -> MockTrackingProvider:
        """Get the tracking provider."""
        provider = self._providers.get("mock_tracking_provider")
        if provider is None:
            raise RuntimeError("Tracking provider not registered")
        return provider  # type: ignore

    def get_amazon_provider(self) -> BaseProvider | None:
        """Get the Amazon sandbox provider (if registered)."""
        return self._providers.get("amazon_order_provider")

    def get_tiktok_provider(self) -> BaseProvider | None:
        """Get the TikTok Shop provider (if registered)."""
        return self._providers.get("tiktok_order_provider")

    def set_pricing_provider(self, provider: PricingProviderBase) -> None:
        """Set the single active pricing provider.

        Unlike order providers (several can coexist, picked per
        order.source), pricing is a single global strategy selected via
        PRICING_PROVIDER — see create_default_registry.
        """
        self._pricing_provider = provider
        logger.info(
            "Pricing provider set: %s (configured=%s)",
            provider.provider_name,
            provider.is_configured,
        )

    def get_pricing_provider(self) -> PricingProviderBase:
        """Get the active pricing provider.

        Always returns a provider (create_default_registry always sets
        one, defaulting to mock) — callers still must check
        provider.is_configured before trusting a non-mock provider's
        result, since "registered" and "configured" are different things
        for pa_api/scrape.
        """
        if self._pricing_provider is None:
            raise RuntimeError("Pricing provider not set")
        return self._pricing_provider

    def set_notification_provider(self, provider: NotificationProviderBase) -> None:
        """Set the single active notification provider — same one-active-
        strategy model as pricing, selected via NOTIFICATION_PROVIDER."""
        self._notification_provider = provider
        logger.info(
            "Notification provider set: %s (configured=%s)",
            provider.provider_name,
            provider.is_configured,
        )

    def get_notification_provider(self) -> NotificationProviderBase:
        """Get the active notification provider. Always returns one
        (create_default_registry always sets one, defaulting to log)."""
        if self._notification_provider is None:
            raise RuntimeError("Notification provider not set")
        return self._notification_provider

    def list_all(self) -> list[dict]:
        """List all registered providers."""
        return [
            {
                "name": p.provider_name,
                "environment": p.environment.value,
                "is_mock": p.is_mock,
                "capabilities": {
                    "supports_order_read": p.capabilities.supports_order_read,
                    "supports_order_list": p.capabilities.supports_order_list,
                    "supports_supplier_prepare": p.capabilities.supports_supplier_prepare,
                    "supports_supplier_verify": p.capabilities.supports_supplier_verify,
                    "supports_supplier_submit": p.capabilities.supports_supplier_submit,
                    "supports_tracking_read": p.capabilities.supports_tracking_read,
                    "supports_fulfillment_update": p.capabilities.supports_fulfillment_update,
                },
            }
            for p in self._providers.values()
        ]

    def clear(self) -> None:
        """Clear all providers (used by tests)."""
        self._providers.clear()


def create_default_registry() -> ProviderRegistry:
    """Create a registry with default mock providers.
    
    CHUNK 1V: Also registers Amazon sandbox provider if credentials available.
    """
    registry = ProviderRegistry()
    registry.register(MockOrderProvider())
    registry.register(MockSupplierProvider())
    registry.register(MockTrackingProvider())
    
    # CHUNK 1V: Try to register Amazon sandbox provider
    try:
        from app.services.providers.amazon.order_provider import AmazonOrderProvider
        amazon_provider = AmazonOrderProvider()
        if amazon_provider.is_configured:
            registry.register(amazon_provider)
            logger.info("Amazon sandbox provider registered (credentials available)")
        else:
            logger.info("Amazon sandbox provider NOT registered (no credentials)")
    except Exception as e:
        logger.info("Amazon sandbox provider registration skipped: %s", type(e).__name__)

    # Try to register TikTok Shop provider (real integration, never mock)
    try:
        from app.services.providers.tiktok.order_provider import TikTokOrderProvider
        tiktok_provider = TikTokOrderProvider()
        if tiktok_provider.is_configured:
            registry.register(tiktok_provider)
            logger.info("TikTok Shop provider registered (credentials available)")
        else:
            logger.info("TikTok Shop provider NOT registered (no credentials)")
    except Exception as e:
        logger.info("TikTok Shop provider registration skipped: %s", type(e).__name__)

    registry.set_pricing_provider(_create_pricing_provider())
    registry.set_notification_provider(_create_notification_provider())

    return registry


def _create_pricing_provider() -> PricingProviderBase:
    """Select the pricing provider named by settings.PRICING_PROVIDER.

    Always returns a provider instance — even pa_api/scrape when unconfigured,
    since "selected but not configured" (is_configured=False, callers must
    check) is a meaningfully different, and equally important, state from
    "not selected at all". Falls back to mock (logging a warning) for an
    unrecognized value rather than raising, matching this module's existing
    fail-safe-to-mock posture for the rest of the registry.
    """
    from app.core.config import settings
    from app.services.providers.amazon.pa_api_pricing import PAAPIPricingProvider
    from app.services.providers.amazon.scrape_pricing import ScrapePricingProvider
    from app.services.providers.mock.mock_pricing import MockPricingProvider

    choice = settings.PRICING_PROVIDER.strip().lower()
    if choice == "pa_api":
        return PAAPIPricingProvider()
    if choice == "scrape":
        return ScrapePricingProvider()
    if choice != "mock":
        logger.warning(
            "Unrecognized PRICING_PROVIDER=%r — falling back to 'mock'. "
            "Valid options: pa_api, mock, scrape.",
            settings.PRICING_PROVIDER,
        )
    return MockPricingProvider()


def _create_notification_provider() -> NotificationProviderBase:
    """Select the notification provider named by settings.NOTIFICATION_PROVIDER.

    Same fail-safe-to-a-known-default posture as _create_pricing_provider:
    an unrecognized value logs a warning and falls back to "log" rather
    than raising.
    """
    from app.core.config import settings
    from app.services.providers.mock.mock_notifications import LogNotificationProvider
    from app.services.providers.slack.webhook import SlackWebhookNotificationProvider

    choice = settings.NOTIFICATION_PROVIDER.strip().lower()
    if choice == "slack":
        return SlackWebhookNotificationProvider()
    if choice != "log":
        logger.warning(
            "Unrecognized NOTIFICATION_PROVIDER=%r — falling back to 'log'. "
            "Valid options: slack, log.",
            settings.NOTIFICATION_PROVIDER,
        )
    return LogNotificationProvider()


# Global registry instance
provider_registry = create_default_registry()
