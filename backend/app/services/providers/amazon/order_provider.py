"""Amazon Order Provider — sandbox integration for CHUNK 1V.

Implements read-only Amazon SP-API integration for sandbox environment.
Connects to Amazon sandbox, retrieves orders, and normalizes them to
internal format for the fulfillment engine.

CRITICAL SAFETY RULES:
- Only sandbox endpoints are allowed
- Production endpoints are blocked
- Read-only operations only
- Credentials are never logged
- PII is redacted at the boundary
- Approval gate remains authoritative

Architecture:
Amazon Sandbox → LWA Auth → SP-API Client → AmazonOrderProvider →
Order Normalization → Existing OrderService → Fulfillment Engine →
WAITING_APPROVAL (STOP — no auto-submit)
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.services.providers.amazon.lwa_auth import (
    LWATokenManager,
    LWAAuthenticationError,
    create_lwa_token_manager_from_env,
)
from app.services.providers.amazon.sp_api_client import (
    SPAPIClient,
    SPAPIError,
)
from app.services.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderEnvironment,
    ProviderOperationNotSupportedError,
    ProviderAuthenticationError,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Amazon Order Provider
# ---------------------------------------------------------------------------

class AmazonOrderProvider(BaseProvider):
    """Amazon order provider for sandbox integration.
    
    This provider:
    - Connects to Amazon SP-API sandbox
    - Retrieves orders using Orders API v2026-01-01
    - Normalizes Amazon responses to internal format
    - Enforces read-only operations
    - Handles authentication via LWA
    
    SAFETY:
    - Only sandbox endpoints allowed
    - Production endpoints blocked at client level
    - Read-only operations enforced
    - Credentials never logged
    - PII redacted at boundary
    
    Architecture:
    Amazon Sandbox → LWA Auth → SP-API Client → This Provider →
    Normalized Orders → OrderService → Fulfillment Engine →
    WAITING_APPROVAL
    """
    
    def __init__(
        self,
        lwa_manager: LWATokenManager | None = None,
        region: str = "na",
        marketplace_id: str = "ATVPDKIKX0DER",
        environment: str | None = None,
    ):
        """Initialize Amazon order provider.
        
        Args:
            lwa_manager: LWA token manager (created from env if None)
            region: AWS region (na, eu, fe)
            marketplace_id: Amazon marketplace ID
            environment: 'sandbox' or 'production' (reads from config if None)
        """
        self._lwa_manager = lwa_manager or create_lwa_token_manager_from_env()
        self._region = region
        self._marketplace_id = marketplace_id
        
        # Determine environment from config if not provided
        if environment is None:
            from app.core.config import settings
            environment = settings.amazon_environment
        self._environment = environment
        
        # Create SP-API client if credentials available
        self._client: SPAPIClient | None = None
        if self._lwa_manager and self._lwa_manager.is_configured:
            try:
                self._client = SPAPIClient(
                    lwa_manager=self._lwa_manager,
                    region=region,
                    marketplace_id=marketplace_id,
                    environment=environment,
                )
                logger.info(
                    "Amazon order provider initialized (region=%s, environment=%s)",
                    region,
                    environment,
                )
            except SPAPIError as e:
                logger.warning("Failed to create SP-API client: %s", e.message)
        
        # Import tracking for idempotency
        self._imported_order_ids: set[str] = set()
        
        # Statistics
        self._orders_retrieved: int = 0
        self._orders_normalized: int = 0
    
    @property
    def provider_name(self) -> str:
        return "amazon_order_provider"
    
    @property
    def environment(self) -> ProviderEnvironment:
        """Amazon environment — sandbox or production."""
        if self._environment == "production":
            return ProviderEnvironment.PRODUCTION
        return ProviderEnvironment.SANDBOX
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        """Read-only capabilities for sandbox."""
        return ProviderCapabilities(
            supports_order_read=True,
            supports_order_list=True,
            # All other capabilities False — read-only
        )
    
    @property
    def is_configured(self) -> bool:
        """Check if provider has valid credentials."""
        return self._client is not None and self._lwa_manager is not None
    
    @property
    def connection_status(self) -> dict:
        """Get connection status for frontend display."""
        return {
            "configured": self.is_configured,
            "sandbox": self._environment == "sandbox",
            "environment": self._environment,
            "mode": "read-only",
            "region": self._region,
            "marketplace_id": self._marketplace_id,
            "credentials_available": self._lwa_manager is not None and self._lwa_manager.is_configured,
            "token_expires_in": self._lwa_manager.token_expires_in if self._lwa_manager else 0,
            "token_refresh_count": self._lwa_manager.refresh_count if self._lwa_manager else 0,
            "request_stats": self._client.request_stats if self._client else None,
            "orders_retrieved": self._orders_retrieved,
            "orders_normalized": self._orders_normalized,
        }
    
    # -----------------------------------------------------------------------
    # Order Operations
    # -----------------------------------------------------------------------
    
    def get_order(self, order_id: str) -> dict | None:
        """Retrieve a single Amazon order by ID.
        
        Args:
            order_id: Amazon Order ID (e.g., "111-1234567-1234567")
            
        Returns:
            Normalized order dict, or None if not found
            
        Raises:
            ProviderAuthenticationError: If not configured
            SPAPIError: If API request fails
        """
        if not self.is_configured:
            logger.info("Amazon provider not configured — returning None")
            return None
        
        logger.info("AmazonOrderProvider: get_order(%s)", order_id)
        
        try:
            response = self._client.get_order_sync(order_id)  # type: ignore
            
            # Extract order from response
            order_data = response.get("payload", response)
            
            # Normalize to internal format
            normalized = self._normalize_order(order_data)
            self._orders_retrieved += 1
            self._orders_normalized += 1
            
            return normalized
            
        except SPAPIError as e:
            if e.status_code == 404:
                logger.info("Amazon order not found: %s", order_id)
                return None
            logger.error("Failed to get Amazon order %s: %s", order_id, e.message)
            raise
    
    def list_orders(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """List Amazon orders.
        
        Args:
            limit: Maximum number of orders to return
            offset: Number of orders to skip
            
        Returns:
            List of normalized order dicts
        """
        if not self.is_configured:
            logger.info("Amazon provider not configured — returning empty list")
            return []
        
        logger.info("AmazonOrderProvider: list_orders(limit=%d, offset=%d)", limit, offset)
        
        try:
            # Use searchOrders to get orders
            response = self._client.search_orders_sync(
                max_results=min(limit + offset, 100),
            )
            
            # Extract orders from response
            orders_data = response.get("payload", {}).get("orders", [])
            
            # Normalize orders
            normalized_orders = []
            for order_data in orders_data:
                normalized = self._normalize_order(order_data)
                if normalized:
                    normalized_orders.append(normalized)
            
            # Apply offset and limit
            result = normalized_orders[offset:offset + limit]
            self._orders_retrieved += len(result)
            self._orders_normalized += len(result)
            
            return result
            
        except SPAPIError as e:
            logger.error("Failed to list Amazon orders: %s", e.message)
            return []
    
    def get_order_count(self) -> int:
        """Return total number of Amazon orders.
        
        This is approximate — actual count requires paginating all results.
        """
        if not self.is_configured:
            return 0
        
        # For sandbox, return a reasonable estimate
        # In production, this would require pagination
        return self._orders_retrieved
    
    def search_orders(
        self,
        *,
        created_after: str | None = None,
        created_before: str | None = None,
        status: str | None = None,
        fulfillment_channel: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search Amazon orders by criteria.
        
        Args:
            created_after: Filter orders created after this ISO timestamp
            created_before: Filter orders created before this ISO timestamp
            status: Filter by Amazon order status
            fulfillment_channel: Filter by channel (MFN, AFN)
            limit: Maximum results
            
        Returns:
            List of Amazon order dicts
        """
        if not self.is_configured:
            return []
        
        logger.info(
            "AmazonOrderProvider: search_orders(created_after=%s, limit=%d)",
            created_after,
            limit,
        )
        
        try:
            # Map status to fulfillmentStatuses
            fulfillment_statuses = None
            if status:
                fulfillment_statuses = [status]
            
            response = self._client.search_orders_sync(
                created_after=created_after,
                created_before=created_before,
                max_results=limit,
            )
            
            orders_data = response.get("payload", {}).get("orders", [])
            
            normalized_orders = []
            for order_data in orders_data:
                normalized = self._normalize_order(order_data)
                if normalized:
                    normalized_orders.append(normalized)
            
            self._orders_retrieved += len(normalized_orders)
            self._orders_normalized += len(normalized_orders)
            
            return normalized_orders
            
        except SPAPIError as e:
            logger.error("Failed to search Amazon orders: %s", e.message)
            return []
    
    # -----------------------------------------------------------------------
    # Order Normalization
    # -----------------------------------------------------------------------
    
    def _normalize_order(self, amazon_order: dict) -> dict | None:
        """Transform Amazon order response to internal format.
        
        This is the KEY transformation:
        Amazon API Response → Internal OrderCreate-compatible dict
        
        Args:
            amazon_order: Amazon order dict (from SP-API)
            
        Returns:
            Normalized order dict, or None if invalid
        """
        if not amazon_order:
            return None
        
        try:
            # Extract order ID
            amazon_order_id = amazon_order.get("amazonOrderId", "")
            if not amazon_order_id:
                logger.warning("Amazon order missing amazonOrderId")
                return None
            
            # Extract order status
            order_status = amazon_order.get("orderStatus", "Unshipped")
            
            # Extract purchase date
            purchase_date = amazon_order.get("purchaseDate", "")
            
            # Extract fulfillment channel
            fulfillment_channel = amazon_order.get("fulfillmentChannel", "MFN")
            
            # Extract shipping address from RECIPIENT data
            recipient = amazon_order.get("recipientAddress", {})
            shipping_address = self._format_address(recipient)
            
            # Extract buyer info (email anonymized for sandbox)
            buyer_email = amazon_order.get("buyerEmail", "")
            if buyer_email:
                # Anonymize email for sandbox display
                parts = buyer_email.split("@")
                if len(parts) == 2:
                    buyer_email = f"***@{parts[1]}"
            
            # For sandbox, use default product info
            # In production, this would come from order items
            product_name = f"Amazon Order {amazon_order_id[-8:]}"
            sku = f"AMZ-{amazon_order_id[-8:]}"
            quantity = 1  # Default for sandbox
            
            return {
                "order_id": amazon_order_id,
                "amazon_order_id": amazon_order_id,
                "sku": sku,
                "product_name": product_name,
                "quantity": quantity,
                "customer_name": buyer_email or "Amazon Customer",
                "shipping_address": shipping_address,
                "order_status": order_status,
                "fulfillment_channel": fulfillment_channel,
                "purchase_date": purchase_date,
                "source": "AMAZON_SANDBOX",
                "marketplace_id": self._marketplace_id,
                "created_at": purchase_date or datetime.now(timezone.utc).isoformat(),
            }
            
        except Exception as e:
            logger.error(
                "Failed to normalize Amazon order: %s",
                type(e).__name__,
            )
            return None
    
    def _format_address(self, recipient: dict) -> str:
        """Format Amazon recipient address to internal format.
        
        Args:
            recipient: Amazon recipient address dict
            
        Returns:
            Formatted address string
        """
        if not recipient:
            return "No address provided"
        
        lines = []
        
        # Name
        name = recipient.get("name", "Amazon Customer")
        lines.append(name)
        
        # Address lines
        address_line_1 = recipient.get("addressLine1", "")
        if address_line_1:
            lines.append(address_line_1)
        
        address_line_2 = recipient.get("addressLine2", "")
        if address_line_2:
            lines.append(address_line_2)
        
        # City, State, Postal Code
        city = recipient.get("city", "")
        state = recipient.get("stateOrRegion", "")
        postal_code = recipient.get("postalCode", "")
        
        city_line = ", ".join(filter(None, [city, state, postal_code]))
        if city_line:
            lines.append(city_line)
        
        # Country
        country = recipient.get("countryCode", "US")
        lines.append(country)
        
        return "\n".join(lines)
    
    # -----------------------------------------------------------------------
    # Import Operations
    # -----------------------------------------------------------------------
    
    def import_orders(
        self,
        order_ids: list[str] | None = None,
    ) -> list[str]:
        """Import Amazon orders with idempotency.
        
        Args:
            order_ids: Specific order IDs to import (None = search recent)
            
        Returns:
            List of successfully imported order IDs
        """
        if not self.is_configured:
            logger.info("Amazon provider not configured — no orders imported")
            return []
        
        imported_ids: list[str] = []
        
        try:
            # Get orders to import
            if order_ids:
                # Import specific orders
                for order_id in order_ids:
                    if order_id in self._imported_order_ids:
                        logger.info("Skipping already imported order: %s", order_id)
                        continue
                    
                    order = self.get_order(order_id)
                    if order:
                        self._imported_order_ids.add(order_id)
                        imported_ids.append(order_id)
                        logger.info("Imported Amazon order: %s", order_id)
            else:
                # Search for recent orders
                orders = self.search_orders(limit=50)
                for order in orders:
                    amazon_id = order.get("amazon_order_id", "")
                    if amazon_id and amazon_id not in self._imported_order_ids:
                        self._imported_order_ids.add(amazon_id)
                        imported_ids.append(amazon_id)
                        logger.info("Imported Amazon order: %s", amazon_id)
            
        except Exception as e:
            logger.error("Failed to import Amazon orders: %s", type(e).__name__)
        
        return imported_ids
    
    def is_order_imported(self, order_id: str) -> bool:
        """Check if an Amazon order has been imported."""
        return order_id in self._imported_order_ids
    
    def clear_imports(self) -> None:
        """Clear import tracking (used by tests)."""
        self._imported_order_ids.clear()
        self._orders_retrieved = 0
        self._orders_normalized = 0
    
    # -----------------------------------------------------------------------
    # Utility Methods
    # -----------------------------------------------------------------------
    
    def test_connection(self) -> dict:
        """Test connection to Amazon sandbox.
        
        Returns:
            Connection test results
        """
        if not self.is_configured:
            return {
                "success": False,
                "error": "Not configured — no credentials available",
                "sandbox": self._environment == "sandbox",
                "environment": self._environment,
            }
        
        try:
            # Try to get a token
            access_token = self._lwa_manager.get_access_token_sync()
            return {
                "success": True,
                "sandbox": self._environment == "sandbox",
                "environment": self._environment,
                "token_obtained": True,
                "token_expires_in": self._lwa_manager.token_expires_in,
            }
        except LWAAuthenticationError as e:
            return {
                "success": False,
                "error": e.message,
                "recoverable": e.recoverable,
                "sandbox": self._environment == "sandbox",
                "environment": self._environment,
            }
