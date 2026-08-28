"""Mock Amazon Order Import Service.

Provides a LOCAL/SYNTHETIC Amazon-like order import sandbox that demonstrates
the complete fulfillment pipeline without connecting to Amazon.

ABSOLUTELY NO REAL AMAZON ACCESS. ALL DATA IS LOCAL/SYNTHETIC/MOCK/TEST-ONLY.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.errors import NotFoundError, ValidationError
from app.core.security import redact_pii
from app.schemas.address import AddressProcessingStatus
from app.schemas.fulfillment import FulfillmentStatus
from app.schemas.inventory import InventoryCreate
from app.schemas.order import OrderCreate, OrderStatus
from app.services.address.service import address_processing_service
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.inventory_service import inventory_service
from app.services.order_service import order_service
from app.services.providers.mock.order_provider import mock_order_provider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Audit Event Types
# ---------------------------------------------------------------------------

class MockAmazonAuditEventType:
    MOCK_ORDER_IMPORTED = "MOCK_ORDER_IMPORTED"
    ORDER_MAPPED = "ORDER_MAPPED"
    ADDRESS_PROCESSED = "ADDRESS_PROCESSED"
    INVENTORY_CHECKED = "INVENTORY_CHECKED"
    INVENTORY_RESERVED = "INVENTORY_RESERVED"
    FULFILLMENT_STARTED = "FULFILLMENT_STARTED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    MOCK_SUPPLIER_SUBMITTED = "MOCK_SUPPLIER_SUBMITTED"
    MOCK_TRACKING_CREATED = "MOCK_TRACKING_CREATED"
    FULFILLMENT_COMPLETED = "FULFILLMENT_COMPLETED"
    IMPORT_DUPLICATE_BLOCKED = "IMPORT_DUPLICATE_BLOCKED"
    INVENTORY_INSUFFICIENT = "INVENTORY_INSUFFICIENT"
    ADDRESS_REVIEW_STOPPED = "ADDRESS_REVIEW_STOPPED"


# ---------------------------------------------------------------------------
# Mock Amazon Service
# ---------------------------------------------------------------------------

class MockAmazonService:
    """Orchestrates synthetic Amazon order import through the full fulfillment pipeline.

    Flow:
        MOCK AMAZON ORDER
            ↓ IMPORT
            ↓ ORDER MAPPING
            ↓ ADDRESS PROCESSING
            ↓ INVENTORY CHECK
            ↓ RESERVE INVENTORY
            ↓ PREPARE SUPPLIER ORDER
            ↓ VERIFY SUPPLIER ORDER
            ↓ HUMAN APPROVAL (WAITING)
            ↓ (after approval) MOCK SUPPLIER SUBMISSION
            ↓ MOCK CONFIRMATION
            ↓ MOCK TRACKING

    All operations are local. No external network requests.
    """

    def __init__(self) -> None:
        self._audit_log: list[dict] = []
        self._imported_orders: dict[str, UUID] = {}  # amz_order_id -> internal_order_id
        self._fulfillment_map: dict[str, UUID] = {}  # amz_order_id -> workflow_id

    # ------------------------------------------------------------------
    # Core import operation
    # ------------------------------------------------------------------

    def import_mock_orders(self, organization_id) -> dict:
        """Import synthetic Amazon orders into the system.

        organization_id: the real, authenticated organization performing the
        import (required — there is no default/system organization; see
        app/api/v1/mock_amazon.py's import_mock_orders route).

        Returns summary of import results.
        Never contacts the internet.
        """
        # Get all available mock Amazon orders
        all_amazon_orders = mock_order_provider.get_mock_amazon_orders()
        total_available = len(all_amazon_orders)

        newly_imported = 0
        skipped_duplicates = 0

        # Import at provider level (handles provider-side dedup)
        imported_ids = mock_order_provider.import_mock_orders()

        # Now also check service-level duplicates and map to internal orders
        for order_data in all_amazon_orders:
            amz_order_id = order_data["order_id"]
            if amz_order_id in self._imported_orders:
                skipped_duplicates += 1
                self._audit_event(
                    amz_order_id=amz_order_id,
                    event_type=MockAmazonAuditEventType.IMPORT_DUPLICATE_BLOCKED,
                    details=f"Duplicate import blocked for {amz_order_id}",
                )
                continue

            # Map to internal order
            internal_order = self._map_to_internal_order(order_data, organization_id)
            self._imported_orders[amz_order_id] = internal_order.id
            newly_imported += 1

            self._audit_event(
                amz_order_id=amz_order_id,
                event_type=MockAmazonAuditEventType.MOCK_ORDER_IMPORTED,
                details=f"Imported synthetic order {amz_order_id} (source=MOCK_AMAZON)",
            )
            self._audit_event(
                amz_order_id=amz_order_id,
                event_type=MockAmazonAuditEventType.ORDER_MAPPED,
                details=f"Mapped to internal order {internal_order.id}",
            )

        return {
            "imported": newly_imported,
            "skipped_duplicates": skipped_duplicates,
            "total_amazon_orders": total_available,
            "imported_order_ids": list(self._imported_orders.keys()),
        }

    def get_import_status(self) -> dict:
        """Return current import status."""
        return {
            "total_synthetic_orders": len(mock_order_provider.get_mock_amazon_orders()),
            "imported_count": len(self._imported_orders),
            "imported_order_ids": list(self._imported_orders.keys()),
            "environment": "SANDBOX",
            "source": "MOCK_AMAZON",
        }

    def get_imported_orders(self) -> list[dict]:
        """Return all imported mock Amazon orders with their internal status."""
        results = []
        for amz_id, internal_id in self._imported_orders.items():
            try:
                order = order_service.get(internal_id)
                # Get fulfillment workflow if exists
                workflow_id = self._fulfillment_map.get(amz_id)
                workflow_status = None
                if workflow_id:
                    try:
                        wf = fulfillment_engine.get_workflow(workflow_id)
                        workflow_status = wf.status.value
                    except NotFoundError:
                        pass

                results.append({
                    "amazon_order_id": amz_id,
                    "internal_order_id": str(order.id),
                    "sku": order.sku,
                    "product_name": order.product_name,
                    "quantity": order.quantity,
                    "customer_name": order.customer_name,
                    "status": order.status.value,
                    "inventory_reserved": order.inventory_reserved,
                    "fulfillment_status": workflow_status,
                    "source": "MOCK_AMAZON",
                })
            except NotFoundError:
                logger.error("Order not found for imported ID %s", amz_id)

        return results

    # ------------------------------------------------------------------
    # End-to-end fulfillment for a specific mock Amazon order
    # ------------------------------------------------------------------

    def start_fulfillment(self, amazon_order_id: str, shipping_method: str = "standard") -> dict:
        """Start the fulfillment workflow for a specific mock Amazon order.

        Returns the workflow state or error details.
        """
        if amazon_order_id not in self._imported_orders:
            raise NotFoundError(f"Mock Amazon order '{amazon_order_id}' not found. Import first.")

        # Idempotency check
        if amazon_order_id in self._fulfillment_map:
            workflow_id = self._fulfillment_map[amazon_order_id]
            try:
                existing_wf = fulfillment_engine.get_workflow(workflow_id)
                if existing_wf.status not in (
                    FulfillmentStatus.COMPLETED,
                    FulfillmentStatus.CANCELLED,
                    FulfillmentStatus.FAILED,
                    FulfillmentStatus.EXPIRED,
                ):
                    self._audit_event(
                        amz_order_id=amazon_order_id,
                        event_type=MockAmazonAuditEventType.IMPORT_DUPLICATE_BLOCKED,
                        details=f"Active workflow exists for {amazon_order_id}",
                    )
                    return {
                        "workflow_id": str(workflow_id),
                        "status": existing_wf.status.value,
                        "message": "Existing workflow returned (idempotent)",
                    }
            except NotFoundError:
                pass

        internal_order_id = self._imported_orders[amazon_order_id]

        # Check inventory before starting
        order = order_service.get(internal_order_id)
        if order.sku:
            inv_item = inventory_service.find_by_sku(order.sku)
            if inv_item is None:
                self._audit_event(
                    amz_order_id=amazon_order_id,
                    event_type=MockAmazonAuditEventType.INVENTORY_INSUFFICIENT,
                    details=f"No inventory for SKU {order.sku}",
                )
                raise ValidationError(f"No inventory found for SKU '{order.sku}'")

            self._audit_event(
                amz_order_id=amazon_order_id,
                event_type=MockAmazonAuditEventType.INVENTORY_CHECKED,
                details=f"SKU {order.sku}: available={inv_item.available_quantity}, requested={order.quantity}",
            )

            if inv_item.available_quantity < order.quantity:
                self._audit_event(
                    amz_order_id=amazon_order_id,
                    event_type=MockAmazonAuditEventType.INVENTORY_INSUFFICIENT,
                    details=f"Insufficient inventory: available={inv_item.available_quantity}, requested={order.quantity}",
                )
                raise ValidationError(
                    f"Insufficient inventory for SKU '{order.sku}': "
                    f"available={inv_item.available_quantity}, requested={order.quantity}"
                )

        # Start the fulfillment workflow
        self._audit_event(
            amz_order_id=amazon_order_id,
            event_type=MockAmazonAuditEventType.FULFILLMENT_STARTED,
            details=f"Starting fulfillment for {amazon_order_id}",
        )

        try:
            workflow = fulfillment_engine.start_workflow(internal_order_id, shipping_method)
            self._fulfillment_map[amazon_order_id] = workflow.id

            return {
                "amazon_order_id": amazon_order_id,
                "workflow_id": str(workflow.id),
                "status": workflow.status.value,
                "steps_completed": sum(
                    1 for s in workflow.steps if s.status.value == "completed"
                ),
                "total_steps": len(workflow.steps),
            }
        except Exception as e:
            self._audit_event(
                amz_order_id=amazon_order_id,
                event_type="FULFILLMENT_FAILED",
                details=f"Error: {str(e)[:200]}",
            )
            raise

    def get_fulfillment_status(self, amazon_order_id: str) -> dict:
        """Get fulfillment status for a specific mock Amazon order."""
        if amazon_order_id not in self._imported_orders:
            raise NotFoundError(f"Mock Amazon order '{amazon_order_id}' not found")

        workflow_id = self._fulfillment_map.get(amazon_order_id)
        if workflow_id is None:
            return {
                "amazon_order_id": amazon_order_id,
                "fulfillment_status": "not_started",
                "message": "No fulfillment workflow started",
            }

        workflow = fulfillment_engine.get_workflow(workflow_id)
        return {
            "amazon_order_id": amazon_order_id,
            "workflow_id": str(workflow.id),
            "status": workflow.status.value,
            "current_step": workflow.current_step,
            "steps": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "result": s.result,
                    "error": s.error,
                }
                for s in workflow.steps
            ],
            "confirmation": (
                {
                    "confirmation_id": workflow.confirmation.confirmation_id,
                    "supplier": workflow.confirmation.supplier,
                    "status": workflow.confirmation.status,
                }
                if workflow.confirmation
                else None
            ),
        }

    # ------------------------------------------------------------------
    # Mock tracking
    # ------------------------------------------------------------------

    def generate_mock_tracking(self, amazon_order_id: str) -> dict:
        """Generate synthetic tracking for a completed mock Amazon order.

        Only works for orders with completed fulfillment.
        """
        if amazon_order_id not in self._imported_orders:
            raise NotFoundError(f"Mock Amazon order '{amazon_order_id}' not found")

        workflow_id = self._fulfillment_map.get(amazon_order_id)
        if workflow_id is None:
            raise ValidationError("No fulfillment workflow for this order")

        workflow = fulfillment_engine.get_workflow(workflow_id)
        if workflow.status != FulfillmentStatus.COMPLETED:
            raise ValidationError(
                f"Order fulfillment not completed (status: {workflow.status.value})"
            )

        tracking_id = f"MOCK-TRACK-{uuid4().hex[:6].upper()}"

        self._audit_event(
            amz_order_id=amazon_order_id,
            event_type=MockAmazonAuditEventType.MOCK_TRACKING_CREATED,
            details=f"Generated tracking {tracking_id}",
        )

        return {
            "amazon_order_id": amazon_order_id,
            "tracking_id": tracking_id,
            "carrier": "MOCK-CARRIER",
            "status": "PROCESSING",
            "message": "Synthetic tracking generated (no real carrier contact)",
        }

    # ------------------------------------------------------------------
    # Clear state (for tests)
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all state (used by tests)."""
        self._audit_log.clear()
        self._imported_orders.clear()
        self._fulfillment_map.clear()
        mock_order_provider.clear_amazon_imports()

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def get_audit_log(self, amazon_order_id: str | None = None) -> list[dict]:
        """Return audit events, optionally filtered by Amazon order ID."""
        events = self._audit_log
        if amazon_order_id is not None:
            events = [e for e in events if e["amazon_order_id"] == amazon_order_id]
        return events

    def _audit_event(
        self,
        amz_order_id: str,
        event_type: str,
        details: str = "",
    ) -> None:
        """Record a structured audit event (PII-safe)."""
        safe_details = redact_pii(details)
        event = {
            "id": str(uuid4()),
            "amazon_order_id": amz_order_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": safe_details[:500],
        }
        self._audit_log.append(event)

    # ------------------------------------------------------------------
    # Internal mapping
    # ------------------------------------------------------------------

    def _map_to_internal_order(self, amazon_order: dict, organization_id):
        """Map synthetic Amazon order to internal Order model.

        organization_id is the real, authenticated organization performing
        the import (see import_mock_orders) — the synthetic Amazon data
        stays synthetic, but the order's ownership is real, never a
        default/fabricated tenant.
        """
        order_create = OrderCreate(
            customer_name=amazon_order["customer_name"],
            shipping_address=amazon_order["shipping_address"],
            product_name=amazon_order["product_name"],
            sku=amazon_order.get("sku", ""),
            quantity=amazon_order.get("quantity", 1),
            status=OrderStatus.PENDING,
        )
        return order_service.create(order_create, organization_id)


# Global instance
mock_amazon_service = MockAmazonService()
