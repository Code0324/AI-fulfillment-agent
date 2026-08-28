"""Mock Tracking Provider — local synthetic tracking data.

All data is synthetic. No real carrier APIs (UPS, FedEx, USPS, DHL) are used.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.services.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderEnvironment,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock Tracking Data
# ---------------------------------------------------------------------------

class TrackingStatus:
    """Tracking status constants."""
    PROCESSING = "processing"
    SHIPPED = "shipped"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"


MOCK_TRACKING: dict[str, dict] = {
    "MOCK-TRACK-000001": {
        "tracking_id": "MOCK-TRACK-000001",
        "carrier": "MOCK-CARRIER",
        "status": TrackingStatus.DELIVERED,
        "origin": "New York, NY",
        "destination": "Los Angeles, CA",
        "shipped_at": "2026-01-20T10:00:00Z",
        "delivered_at": "2026-01-25T14:30:00Z",
        "estimated_delivery": "2026-01-27",
        "events": [
            {"timestamp": "2026-01-20T10:00:00Z", "status": "shipped", "location": "New York, NY"},
            {"timestamp": "2026-01-22T08:00:00Z", "status": "in_transit", "location": "Chicago, IL"},
            {"timestamp": "2026-01-24T16:00:00Z", "status": "out_for_delivery", "location": "Los Angeles, CA"},
            {"timestamp": "2026-01-25T14:30:00Z", "status": "delivered", "location": "Los Angeles, CA"},
        ],
    },
    "MOCK-TRACK-000002": {
        "tracking_id": "MOCK-TRACK-000002",
        "carrier": "MOCK-CARRIER",
        "status": TrackingStatus.IN_TRANSIT,
        "origin": "Chicago, IL",
        "destination": "Houston, TX",
        "shipped_at": "2026-01-22T09:00:00Z",
        "delivered_at": None,
        "estimated_delivery": "2026-01-28",
        "events": [
            {"timestamp": "2026-01-22T09:00:00Z", "status": "shipped", "location": "Chicago, IL"},
            {"timestamp": "2026-01-24T12:00:00Z", "status": "in_transit", "location": "Memphis, TN"},
        ],
    },
    "MOCK-TRACK-000003": {
        "tracking_id": "MOCK-TRACK-000003",
        "carrier": "MOCK-CARRIER",
        "status": TrackingStatus.PROCESSING,
        "origin": "Seattle, WA",
        "destination": "Denver, CO",
        "shipped_at": None,
        "delivered_at": None,
        "estimated_delivery": "2026-01-30",
        "events": [
            {"timestamp": "2026-01-25T11:00:00Z", "status": "processing", "location": "Seattle, WA"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Mock Tracking Provider
# ---------------------------------------------------------------------------

class MockTrackingProvider(BaseProvider):
    """Local mock tracking provider using synthetic data.

    No real carrier APIs (UPS, FedEx, USPS, DHL) are used.
    All data is hardcoded for testing purposes.
    """

    @property
    def provider_name(self) -> str:
        return "mock_tracking_provider"

    @property
    def environment(self) -> ProviderEnvironment:
        return ProviderEnvironment.MOCK

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_tracking_read=True,
        )

    def get_tracking(self, tracking_id: str) -> dict | None:
        """Retrieve tracking information by ID."""
        logger.info("MockTrackingProvider: get_tracking(%s)", tracking_id)
        return MOCK_TRACKING.get(tracking_id)

    def get_status(self, tracking_id: str) -> str | None:
        """Get current tracking status."""
        tracking = self.get_tracking(tracking_id)
        if tracking is None:
            return None
        return tracking.get("status")

    def list_tracking(self, *, limit: int = 100, offset: int = 0) -> list[dict]:
        """List all mock tracking records."""
        all_tracking = list(MOCK_TRACKING.values())
        return all_tracking[offset:offset + limit]

    def generate_tracking_id(self) -> str:
        """Generate a new synthetic tracking ID."""
        return f"MOCK-TRACK-{uuid4().hex[:6].upper()}"


# Global instance
mock_tracking_provider = MockTrackingProvider()
