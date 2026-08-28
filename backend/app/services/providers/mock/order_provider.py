"""Mock Order Provider — local synthetic order data.

All data is synthetic. No real Amazon or external order data is used.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.errors import NotFoundError
from app.services.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderEnvironment,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock Order Data
# ---------------------------------------------------------------------------

MOCK_ORDERS: dict[str, dict] = {
    "MOCK-ORDER-001": {
        "order_id": "MOCK-ORDER-001",
        "sku": "SKU-TEST-001",
        "product_name": "Wireless Mouse",
        "quantity": 5,
        "customer_name": "Test Customer",
        "shipping_address": "Test Customer\n123 Test Street\nNew York NY 10003\nUS",
        "status": "pending",
        "created_at": "2026-01-15T10:00:00Z",
    },
    "MOCK-ORDER-002": {
        "order_id": "MOCK-ORDER-002",
        "sku": "SKU-TEST-002",
        "product_name": "USB Cable",
        "quantity": 10,
        "customer_name": "Demo User",
        "shipping_address": "Demo User\n456 Demo Ave\nLos Angeles CA 90001\nUS",
        "status": "pending",
        "created_at": "2026-01-16T14:30:00Z",
    },
    "MOCK-ORDER-003": {
        "order_id": "MOCK-ORDER-003",
        "sku": "SKU-TEST-003",
        "product_name": "Phone Case",
        "quantity": 2,
        "customer_name": "Sample Person",
        "shipping_address": "Sample Person\n789 Sample Blvd\nChicago IL 60601\nUS",
        "status": "processing",
        "created_at": "2026-01-17T09:15:00Z",
    },
}


# ---------------------------------------------------------------------------
# Synthetic Amazon-shaped Order Data
# ---------------------------------------------------------------------------
# All data is LOCAL, SYNTHETIC, MOCK, TEST-ONLY.
# These are NOT real Amazon order IDs.
# SOURCE = MOCK_AMAZON

MOCK_AMAZON_ORDERS: list[dict] = [
    {
        "order_id": "AMZ-MOCK-0001",
        "sku": "MOCK-SKU-001",
        "product_name": "Synthetic Widget Alpha",
        "quantity": 2,
        "customer_name": "Alice Synthetic",
        "shipping_address": "Alice Synthetic\n100 Mock Lane\nSeattle WA 98101\nUS",
        "phone": "206-555-0101",
        "order_status": "pending",
        "source": "MOCK_AMAZON",
        "created_at": "2026-08-01T10:00:00Z",
    },
    {
        "order_id": "AMZ-MOCK-0002",
        "sku": "MOCK-SKU-002",
        "product_name": "Synthetic Widget Beta",
        "quantity": 1,
        "customer_name": "Bob Synthetic",
        "shipping_address": "Bob Synthetic\n200 Test Drive\nPortland OR 97201\nUS",
        "phone": "503-555-0202",
        "order_status": "pending",
        "source": "MOCK_AMAZON",
        "created_at": "2026-08-02T11:30:00Z",
    },
    {
        "order_id": "AMZ-MOCK-0003",
        "sku": "MOCK-SKU-003",
        "product_name": "Synthetic Widget Gamma",
        "quantity": 3,
        "customer_name": "Carol Synthetic",
        "shipping_address": "Carol Synthetic\n300 Sample St\nSan Francisco CA 94105\nUS",
        "phone": "415-555-0303",
        "order_status": "pending",
        "source": "MOCK_AMAZON",
        "created_at": "2026-08-03T09:15:00Z",
    },
    {
        "order_id": "AMZ-MOCK-0004",
        "sku": "MOCK-SKU-004",
        "product_name": "Synthetic Widget Delta",
        "quantity": 5,
        "customer_name": "Dave Synthetic",
        "shipping_address": "Dave Synthetic\n400 Demo Blvd\nDenver CO 80201\nUS",
        "phone": "720-555-0404",
        "order_status": "pending",
        "source": "MOCK_AMAZON",
        "created_at": "2026-08-04T14:45:00Z",
    },
    {
        "order_id": "AMZ-MOCK-0005",
        "sku": "MOCK-SKU-001",
        "product_name": "Synthetic Widget Alpha",
        "quantity": 1,
        "customer_name": "Eve Synthetic",
        "shipping_address": "Eve Synthetic\n500 Fake Ave\nAustin TX 73301\nUS",
        "phone": "512-555-0505",
        "order_status": "pending",
        "source": "MOCK_AMAZON",
        "created_at": "2026-08-05T16:00:00Z",
    },
]


# ---------------------------------------------------------------------------
# Mock Order Provider
# ---------------------------------------------------------------------------

class MockOrderProvider(BaseProvider):
    """Local mock order provider using synthetic data.

    No real Amazon or external order data is used.
    All data is hardcoded for testing purposes.
    """

    def __init__(self) -> None:
        self._imported_amazon_ids: set[str] = set()

    @property
    def provider_name(self) -> str:
        return "mock_order_provider"

    @property
    def environment(self) -> ProviderEnvironment:
        return ProviderEnvironment.MOCK

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_order_read=True,
            supports_order_list=True,
        )

    def get_order(self, order_id: str) -> dict | None:
        """Retrieve an order by ID from local mock data."""
        logger.info("MockOrderProvider: get_order(%s)", order_id)
        return MOCK_ORDERS.get(order_id)

    def list_orders(self, *, limit: int = 100, offset: int = 0) -> list[dict]:
        """List all mock orders."""
        logger.info("MockOrderProvider: list_orders(limit=%d, offset=%d)", limit, offset)
        all_orders = list(MOCK_ORDERS.values())
        return all_orders[offset:offset + limit]

    def get_order_count(self) -> int:
        """Return total number of mock orders."""
        return len(MOCK_ORDERS)

    # ------------------------------------------------------------------
    # Synthetic Amazon Order Import
    # ------------------------------------------------------------------

    def get_mock_amazon_orders(self) -> list[dict]:
        """Return all synthetic Amazon-shaped orders."""
        return list(MOCK_AMAZON_ORDERS)

    def import_mock_orders(self) -> list[str]:
        """Import synthetic Amazon orders, preventing duplicates.

        Returns list of successfully imported order IDs.
        Never contacts the internet.
        """
        imported_ids: list[str] = []
        for order in MOCK_AMAZON_ORDERS:
            order_id = order["order_id"]
            if order_id in self._imported_amazon_ids:
                logger.info("MockOrderProvider: skipping duplicate %s", order_id)
                continue
            self._imported_amazon_ids.add(order_id)
            imported_ids.append(order_id)
            logger.info("MockOrderProvider: imported %s (source=MOCK_AMAZON)", order_id)
        return imported_ids

    def is_amazon_order_imported(self, order_id: str) -> bool:
        """Check if a mock Amazon order has been imported."""
        return order_id in self._imported_amazon_ids

    def clear_amazon_imports(self) -> None:
        """Clear import tracking (used by tests)."""
        self._imported_amazon_ids.clear()


# Global instance
mock_order_provider = MockOrderProvider()
