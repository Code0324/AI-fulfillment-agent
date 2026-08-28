"""Mock Supplier Provider — local sandbox supplier operations.

All data is synthetic. No real supplier API or accounts are used.
This provider interacts only with the existing local supplier sandbox.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.services.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderEnvironment,
    ProviderSubmissionBlockedError,
    ensure_mock_mode,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock Supplier Provider
# ---------------------------------------------------------------------------

class MockSupplierProvider(BaseProvider):
    """Local mock supplier provider.

    Interacts only with the existing local supplier sandbox.
    No real supplier API or accounts are used.
    All confirmations are synthetic.
    """

    def __init__(self) -> None:
        self._submitted_confirmations: set[str] = set()

    @property
    def provider_name(self) -> str:
        return "mock_supplier_provider"

    @property
    def environment(self) -> ProviderEnvironment:
        return ProviderEnvironment.MOCK

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_supplier_prepare=True,
            supports_supplier_verify=True,
            supports_supplier_submit=True,
        )

    def prepare_order(self, payload: dict) -> dict:
        """Prepare a supplier order from normalized data.

        This is a SAFE operation — no external calls.
        """
        ensure_mock_mode()
        logger.info("MockSupplierProvider: prepare_order(sku=%s)", payload.get("sku", "unknown"))

        return {
            "prepared": True,
            "supplier": "MOCK SUPPLIER",
            "sku": payload.get("sku", "UNKNOWN"),
            "product_name": payload.get("product_name", "Unknown Product"),
            "quantity": payload.get("quantity", 0),
            "shipping_method": payload.get("shipping_method", "standard"),
            "prepared_at": datetime.now(timezone.utc).isoformat(),
        }

    def verify_order(self, prepared_order: dict) -> dict:
        """Verify a prepared order before submission.

        This is a SAFE operation — no external calls.
        """
        ensure_mock_mode()
        logger.info("MockSupplierProvider: verify_order(sku=%s)", prepared_order.get("sku", "unknown"))

        issues = []
        if not prepared_order.get("sku") or prepared_order.get("sku") == "UNKNOWN":
            issues.append("Missing SKU")
        if prepared_order.get("quantity", 0) < 1:
            issues.append("Invalid quantity")

        return {
            "verified": len(issues) == 0,
            "issues": issues,
            "supplier": "MOCK SUPPLIER",
        }

    def submit_order(self, prepared_order: dict, *, approved: bool = False) -> dict:
        """Submit an order to the mock supplier.

        This is a HIGH-RISK operation that requires approval.
        """
        ensure_mock_mode()

        if not approved:
            raise ProviderSubmissionBlockedError(
                "Supplier submission requires human approval"
            )

        logger.info("MockSupplierProvider: submit_order(sku=%s)", prepared_order.get("sku", "unknown"))

        # Generate synthetic confirmation ID
        confirmation_id = f"SUP-MOCK-{uuid4().hex[:6].upper()}"

        # Prevent duplicate submissions
        if confirmation_id in self._submitted_confirmations:
            raise ProviderSubmissionBlockedError(
                f"Duplicate submission detected: {confirmation_id}"
            )
        self._submitted_confirmations.add(confirmation_id)

        return {
            "submitted": True,
            "confirmation_id": confirmation_id,
            "supplier": "MOCK SUPPLIER",
            "status": "submitted",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "estimated_delivery": "5-7 business days",
        }

    def is_duplicate_submission(self, confirmation_id: str) -> bool:
        """Check if a confirmation ID was already submitted."""
        return confirmation_id in self._submitted_confirmations

    def clear(self) -> None:
        """Clear submission history (used by tests)."""
        self._submitted_confirmations.clear()


# Global instance
mock_supplier_provider = MockSupplierProvider()
