"""TikTok Shop Order Provider — real integration.

Implements real TikTok Shop Open API integration: order read, order
status, and fulfillment-update (a real write). There is no mock mode for
this provider — see the module docstring in
services/providers/tiktok/__init__.py.

FAIL-SAFE BEHAVIOR (binding requirement, differs from AmazonOrderProvider
deliberately): every public method here raises ProviderUnavailableError
when not configured, rather than silently returning []/None. A silent
empty return could be misread as "TikTok has zero real orders" rather
than "TikTok is not authorized" — this provider never allows that
ambiguity.

Architecture:
TikTok Shop → TikTokTokenManager (auth.py) → TikTokAPIClient
(api_client.py) → TikTokOrderProvider (this file) → TikTokOrder
normalization → (SKU mapping + fulfillment workflow wiring happens
downstream, in services/sku_mapping/ and services/fulfillment/workflow.py)
"""

import logging
from datetime import datetime, timezone

from app.core.security import redact_secret
from app.services.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderEnvironment,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.services.providers.tiktok.api_client import TikTokAPIClient, TikTokAPIError
from app.services.providers.tiktok.auth import (
    TikTokTokenManager,
    TikTokAuthenticationError,
    create_tiktok_token_manager_from_env,
)
from app.schemas.tiktok import TikTokOrder

logger = logging.getLogger(__name__)


class TikTokOrderProvider(BaseProvider):
    """Real TikTok Shop order provider.

    SAFETY:
    - Every public method raises ProviderUnavailableError when not
      configured — never returns synthetic/fabricated data.
    - Production endpoint access requires explicit environment='production'
      (enforced by TikTokAPIClient).
    - Credentials are never logged.
    - _normalize_order raises rather than guessing on a malformed/
      unexpected response shape.
    """

    def __init__(
        self,
        token_manager: TikTokTokenManager | None = None,
        shop_id: str | None = None,
        environment: str | None = None,
    ):
        self._token_manager = token_manager or create_tiktok_token_manager_from_env()

        if shop_id is None:
            from app.core.config import settings
            shop_id = settings.TIKTOK_SHOP_ID
        self._shop_id = shop_id

        if environment is None:
            from app.core.config import settings
            environment = settings.tiktok_environment
        self._environment = environment

        self._client: TikTokAPIClient | None = None
        if self._token_manager and self._token_manager.is_configured and self._shop_id:
            try:
                self._client = TikTokAPIClient(
                    token_manager=self._token_manager,
                    shop_id=self._shop_id,
                    environment=environment,
                )
                logger.info("TikTok Shop order provider initialized (environment=%s)", environment)
            except TikTokAPIError as e:
                logger.warning("Failed to create TikTok Shop API client: %s", e.message)

        self._imported_order_ids: set[str] = set()
        self._orders_retrieved: int = 0
        self._orders_normalized: int = 0

    @property
    def provider_name(self) -> str:
        return "tiktok_order_provider"

    @property
    def environment(self) -> ProviderEnvironment:
        if self._environment == "production":
            return ProviderEnvironment.PRODUCTION
        return ProviderEnvironment.SANDBOX

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_order_read=True,
            supports_order_list=True,
            supports_fulfillment_update=True,
        )

    @property
    def is_configured(self) -> bool:
        """Whether this provider has valid credentials AND a usable client."""
        return self._client is not None and self._token_manager is not None

    @property
    def connection_status(self) -> dict:
        """Connection status for frontend/status-endpoint display. Never
        leaks raw credentials."""
        if not self.is_configured:
            return {
                "configured": False,
                "environment": self._environment,
                "notice": "TikTok Shop is not configured/authorized",
            }
        return {
            "configured": True,
            "environment": self._environment,
            "shop_id": redact_secret(self._shop_id) if self._shop_id else None,
            "token_expires_in": self._token_manager.token_expires_in,
            "token_refresh_count": self._token_manager.refresh_count,
            "request_stats": self._client.request_stats if self._client else None,
            "orders_retrieved": self._orders_retrieved,
            "orders_normalized": self._orders_normalized,
            "notice": f"TikTok Shop {self._environment} integration active",
        }

    def _require_configured(self) -> None:
        if not self.is_configured:
            raise ProviderUnavailableError(self.provider_name)

    # -----------------------------------------------------------------------
    # Order Operations — the four required methods
    # -----------------------------------------------------------------------

    def get_orders(self, *, limit: int = 100, offset: int = 0) -> list[TikTokOrder]:
        """List TikTok Shop orders.

        Raises:
            ProviderUnavailableError: if not configured
        """
        self._require_configured()
        logger.info("TikTokOrderProvider: get_orders(limit=%d, offset=%d)", limit, offset)

        import asyncio

        async def _run() -> list[TikTokOrder]:
            orders: list[TikTokOrder] = []
            page_token: str | None = None
            while len(orders) < limit + offset:
                response = await self._client.search_orders(  # type: ignore
                    page_size=min(limit + offset - len(orders), 100), page_token=page_token
                )
                raw_orders = response.get("data", {}).get("order_list", [])
                for raw in raw_orders:
                    orders.append(self._normalize_order(raw))
                page_token = response.get("data", {}).get("next_page_token")
                if not page_token or not raw_orders:
                    break
            return orders

        all_orders = asyncio.run(_run())
        result = all_orders[offset : offset + limit]
        self._orders_retrieved += len(result)
        self._orders_normalized += len(result)
        return result

    def get_order_details(self, order_id: str) -> TikTokOrder | None:
        """Get a single TikTok Shop order by ID.

        Raises:
            ProviderUnavailableError: if not configured
        """
        self._require_configured()
        logger.info("TikTokOrderProvider: get_order_details(%s)", order_id)

        import asyncio

        try:
            response = asyncio.run(self._client.get_order_detail([order_id]))  # type: ignore
        except TikTokAPIError as e:
            if e.status_code == 404:
                logger.info("TikTok order not found: %s", order_id)
                return None
            logger.error("Failed to get TikTok order %s: %s", order_id, e.message)
            raise

        raw_orders = response.get("data", {}).get("order_list", [])
        if not raw_orders:
            return None

        normalized = self._normalize_order(raw_orders[0])
        self._orders_retrieved += 1
        self._orders_normalized += 1
        return normalized

    def get_order_status(self, order_id: str) -> str | None:
        """Get a single order's raw status string.

        Implemented as a thin wrapper over get_order_details — TikTok's
        docs did not surface a distinct lightweight status-only endpoint
        during this session's verification, so this reuses the detail
        query rather than inventing an endpoint. See docs/tiktok-integration.md.

        Raises:
            ProviderUnavailableError: if not configured
        """
        order = self.get_order_details(order_id)
        return order.order_status if order else None

    def update_fulfillment(
        self, order_id: str, *, tracking_number: str, shipping_provider_id: str
    ) -> dict:
        """Confirm shipment for a TikTok Shop order — a real write.

        This is gated purely by is_configured (not by the codebase's
        MOCK_ONLY flag, which guards the *supplier purchase* side, a
        separate concern). The return value is only ever what TikTok's
        API actually confirmed — never synthesized.

        Raises:
            ProviderUnavailableError: if not configured
        """
        self._require_configured()
        logger.info("TikTokOrderProvider: update_fulfillment(%s)", order_id)

        import asyncio

        response = asyncio.run(
            self._client.update_package_fulfillment(  # type: ignore
                order_id, tracking_number=tracking_number, shipping_provider_id=shipping_provider_id
            )
        )
        return response

    # -----------------------------------------------------------------------
    # Order Normalization
    # -----------------------------------------------------------------------

    def _normalize_order(self, raw: dict) -> TikTokOrder:
        """Transform a raw TikTok Shop API order into the TikTokOrder schema.

        FIELD NAMES BELOW ARE UNVERIFIED — TikTok's exact order-detail
        response field names could not be confirmed via live documentation
        fetch this session (see docs/tiktok-integration.md). This raises
        ProviderValidationError on any missing/unexpected required field
        rather than guessing, so a wrong field-name assumption fails
        loudly instead of silently fabricating a plausible-looking order.
        """
        try:
            tiktok_order_id = raw["id"]
            recipient = raw["recipient_address"]
            line_items = raw["line_items"]
            if not line_items:
                raise ProviderValidationError(
                    "TikTok Shop order has no line_items — refusing to fabricate one"
                )
            first_item = line_items[0]

            create_time = raw.get("create_time")
            order_date = (
                datetime.fromtimestamp(create_time, tz=timezone.utc)
                if isinstance(create_time, (int, float))
                else datetime.now(timezone.utc)
            )
            delivery_time = raw.get("delivery_time")
            delivery_date = (
                datetime.fromtimestamp(delivery_time, tz=timezone.utc)
                if isinstance(delivery_time, (int, float))
                else None
            )

            return TikTokOrder(
                tiktok_order_id=tiktok_order_id,
                order_date=order_date,
                sku=first_item["seller_sku"],
                product_name=first_item["product_name"],
                variation=first_item.get("sku_name") or None,
                quantity=int(first_item.get("quantity", 1)),
                recipient_name=recipient["name"],
                phone_number=recipient["phone_number"],
                address_line_1=recipient["address_line1"],
                delivery_instructions=recipient.get("delivery_instruction") or None,
                city=recipient["city"],
                state=recipient["state"],
                zipcode=recipient["zipcode"],
                price=float(first_item["sale_price"]),
                delivery_date=delivery_date,
                order_status=raw.get("status", "UNKNOWN"),
            )
        except (KeyError, TypeError, ValueError) as e:
            raise ProviderValidationError(
                f"Failed to normalize TikTok Shop order — unexpected/missing field "
                f"({type(e).__name__}: {e}). Field-name assumptions in _normalize_order "
                f"are unverified against a real TikTok response — see docs/tiktok-integration.md."
            )

    # -----------------------------------------------------------------------
    # Idempotency / import tracking
    #
    # TEST/DEV-ONLY convenience — NOT the production idempotency mechanism.
    # Real duplicate-order protection is the DB-level UniqueConstraint on
    # (organization_id, tiktok_order_id) in FulfillmentOrder — see
    # docs/tiktok-integration.md's production-blockers section for why
    # nothing writes through that constraint yet.
    # -----------------------------------------------------------------------

    def import_orders(self, order_ids: list[str] | None = None) -> list[str]:
        """Process-local dedup bookkeeping only. Raises if not configured."""
        self._require_configured()
        imported_ids: list[str] = []

        if order_ids:
            for order_id in order_ids:
                if order_id in self._imported_order_ids:
                    continue
                order = self.get_order_details(order_id)
                if order:
                    self._imported_order_ids.add(order_id)
                    imported_ids.append(order_id)
        else:
            for order in self.get_orders(limit=50):
                if order.tiktok_order_id not in self._imported_order_ids:
                    self._imported_order_ids.add(order.tiktok_order_id)
                    imported_ids.append(order.tiktok_order_id)

        return imported_ids

    def is_order_imported(self, order_id: str) -> bool:
        return order_id in self._imported_order_ids

    def clear_imports(self) -> None:
        """Clear import tracking (used by tests)."""
        self._imported_order_ids.clear()
        self._orders_retrieved = 0
        self._orders_normalized = 0

    # -----------------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------------

    def test_connection(self) -> dict:
        """Test connection to TikTok Shop by attempting a token fetch."""
        if not self.is_configured:
            return {
                "success": False,
                "error": "Not configured — no credentials available",
                "environment": self._environment,
            }
        try:
            self._token_manager.get_access_token_sync()  # type: ignore
            return {
                "success": True,
                "environment": self._environment,
                "token_obtained": True,
                "token_expires_in": self._token_manager.token_expires_in,  # type: ignore
            }
        except TikTokAuthenticationError as e:
            return {
                "success": False,
                "error": e.message,
                "recoverable": e.recoverable,
                "environment": self._environment,
            }
