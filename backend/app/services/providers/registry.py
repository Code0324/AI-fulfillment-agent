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

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Central registry for all providers.

    In CHUNK 1V:
    - Mock providers are always registered
    - Amazon sandbox provider is registered when credentials are available
    """

    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

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

    return registry


# Global registry instance
provider_registry = create_default_registry()
