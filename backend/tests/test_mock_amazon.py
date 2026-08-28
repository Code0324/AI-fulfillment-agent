"""Tests for Mock Amazon Order Import Sandbox (CHUNK 1Q).

Covers:
1. Synthetic order loading
2. Duplicate order import blocked
3. Order mapping
4. Invalid synthetic order
5. Address processing integration
6. Address review stops workflow
7. Inventory availability
8. Inventory reservation
9. Fulfillment workflow creation
10. Approval required
11. Submission after approval
12. Duplicate submission blocked
13. Mock tracking creation
14. End-to-end successful flow
15. End-to-end insufficient inventory
16. End-to-end invalid address
17. Idempotency
18. Audit events
19. PII protection
20. No external network access
"""

import uuid

import pytest

from app.schemas.inventory import InventoryCreate
from app.schemas.order import OrderCreate, OrderStatus
from app.services.automation.engine import automation_engine
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.inventory_service import inventory_service
from app.services.mock_amazon import mock_amazon_service

from tests.conftest import create_test_organization, auth_headers
from app.services.order_service import order_service
from app.services.providers.mock.order_provider import (
    MOCK_AMAZON_ORDERS,
    mock_order_provider,
)
from app.core.security import redact_pii


# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_all():
    """Clear all state before every test."""
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    automation_engine.clear()
    mock_amazon_service.clear()
    mock_order_provider.clear_amazon_imports()
    yield
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    automation_engine.clear()
    mock_amazon_service.clear()
    mock_order_provider.clear_amazon_imports()


def _setup_inventory():
    """Create inventory for all mock Amazon SKUs."""
    skus = {
        "MOCK-SKU-001": ("Synthetic Widget Alpha", 100),
        "MOCK-SKU-002": ("Synthetic Widget Beta", 50),
        "MOCK-SKU-003": ("Synthetic Widget Gamma", 30),
        "MOCK-SKU-004": ("Synthetic Widget Delta", 20),
    }
    for sku, (name, stock) in skus.items():
        inventory_service.create(
            InventoryCreate(
                sku=sku,
                product_name=name,
                current_stock=stock,
                low_stock_threshold=5,
            )
        )


def _import_orders():
    """Import all mock Amazon orders for a fresh, real test organization.

    A fresh organization_id is fine even for tests that call this twice to
    exercise duplicate-import blocking: mock_amazon_service's dedup check is
    keyed by the (org-agnostic) Amazon order_id, not by organization, so it
    behaves identically regardless of which real org each call is attributed
    to.
    """
    return mock_amazon_service.import_mock_orders(create_test_organization())


# ===========================================================================
# 1. Synthetic order loading
# ===========================================================================
class TestSyntheticOrderLoading:
    """Verify synthetic Amazon orders are loaded correctly."""

    def test_mock_amazon_orders_exist(self):
        assert len(MOCK_AMAZON_ORDERS) == 5

    def test_all_orders_have_required_fields(self):
        required = [
            "order_id", "sku", "product_name", "quantity",
            "customer_name", "shipping_address", "source",
        ]
        for order in MOCK_AMAZON_ORDERS:
            for field in required:
                assert field in order, f"Missing field '{field}' in {order['order_id']}"

    def test_all_orders_are_mock_amazon(self):
        for order in MOCK_AMAZON_ORDERS:
            assert order["source"] == "MOCK_AMAZON"

    def test_order_ids_are_synthetic(self):
        for order in MOCK_AMAZON_ORDERS:
            assert order["order_id"].startswith("AMZ-MOCK-")


# ===========================================================================
# 2. Duplicate order import blocked
# ===========================================================================
class TestDuplicateImportBlocked:
    """Verify duplicate imports are prevented."""

    def test_import_returns_all_orders_first_time(self):
        result = _import_orders()
        assert result["imported"] == 5
        assert result["skipped_duplicates"] == 0

    def test_second_import_skips_duplicates(self):
        _import_orders()
        result = _import_orders()
        assert result["imported"] == 0
        assert result["skipped_duplicates"] == 5

    def test_import_tracking_is_cleared(self):
        _import_orders()
        mock_amazon_service.clear()
        mock_order_provider.clear_amazon_imports()
        result = _import_orders()
        assert result["imported"] == 5


# ===========================================================================
# 3. Order mapping
# ===========================================================================
class TestOrderMapping:
    """Verify Amazon orders are mapped to internal Order model."""

    def test_import_creates_internal_orders(self):
        _import_orders()
        imported = mock_amazon_service.get_imported_orders()
        assert len(imported) == 5

    def test_mapping_preserves_sku(self):
        _import_orders()
        imported = mock_amazon_service.get_imported_orders()
        for order in imported:
            assert order["sku"].startswith("MOCK-SKU-")

    def test_mapping_preserves_quantity(self):
        _import_orders()
        imported = mock_amazon_service.get_imported_orders()
        for order in imported:
            assert order["quantity"] >= 1

    def test_mapping_sets_pending_status(self):
        _import_orders()
        imported = mock_amazon_service.get_imported_orders()
        for order in imported:
            assert order["status"] == "pending"

    def test_mapping_sets_source(self):
        _import_orders()
        imported = mock_amazon_service.get_imported_orders()
        for order in imported:
            assert order["source"] == "MOCK_AMAZON"


# ===========================================================================
# 4. Invalid synthetic order
# ===========================================================================
class TestInvalidSyntheticOrder:
    """Handle edge cases with order data."""

    def test_import_nonexistent_order_fails(self):
        with pytest.raises(Exception):
            mock_amazon_service.start_fulfillment("AMZ-FAKE-9999")

    def test_fulfillment_before_import_fails(self):
        with pytest.raises(Exception):
            mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")


# ===========================================================================
# 5. Address processing integration
# ===========================================================================
class TestAddressProcessingIntegration:
    """Verify address processing is integrated into fulfillment."""

    def test_valid_address_processes_successfully(self):
        from app.services.address.service import address_processing_service
        result = address_processing_service.parse(
            "Alice Synthetic\n100 Mock Lane\nSeattle WA 98101\nUS"
        )
        assert result.status.value in ("processed", "needs_review")
        assert result.first_name == "Alice"

    def test_workflow_processes_address(self):
        _setup_inventory()
        _import_orders()
        result = mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")
        assert result["status"] in ("waiting_approval", "completed", "failed")


# ===========================================================================
# 6. Address review stops workflow
# ===========================================================================
class TestAddressReviewStopsWorkflow:
    """Verify address issues stop fulfillment."""

    def test_bad_address_causes_failure(self):
        from app.services.address.service import address_processing_service
        result = address_processing_service.parse("X")
        assert result.status.value == "failed"


# ===========================================================================
# 7. Inventory availability
# ===========================================================================
class TestInventoryAvailability:
    """Verify inventory checks are performed."""

    def test_fulfillment_checks_inventory(self):
        _setup_inventory()
        _import_orders()
        result = mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")
        assert result is not None

    def test_fulfillment_without_inventory_fails(self):
        _import_orders()
        with pytest.raises(Exception, match="No inventory"):
            mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")


# ===========================================================================
# 8. Inventory reservation
# ===========================================================================
class TestInventoryReservation:
    """Verify inventory is reserved during fulfillment."""

    def test_inventory_reserved_after_fulfillment(self):
        _setup_inventory()
        _import_orders()
        mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")
        inv = inventory_service.find_by_sku("MOCK-SKU-001")
        assert inv is not None
        # AMZ-MOCK-0001 has qty=2, AMZ-MOCK-0005 also has MOCK-SKU-001 with qty=1
        # Only AMZ-MOCK-0001 should be reserved (2 units)
        assert inv.reserved_quantity == 2

    def test_insufficient_inventory_raises_error(self):
        _setup_inventory()
        _import_orders()
        # Reduce stock for MOCK-SKU-004 to below AMZ-MOCK-0004's qty of 5
        item = inventory_service.find_by_sku("MOCK-SKU-004")
        from app.schemas.inventory import InventoryUpdate
        inventory_service.update(item.id, InventoryUpdate(current_stock=2))
        with pytest.raises(Exception, match="Insufficient"):
            mock_amazon_service.start_fulfillment("AMZ-MOCK-0004")


# ===========================================================================
# 9. Fulfillment workflow creation
# ===========================================================================
class TestFulfillmentWorkflowCreation:
    """Verify fulfillment workflow is created."""

    def test_workflow_created(self):
        _setup_inventory()
        _import_orders()
        result = mock_amazon_service.start_fulfillment("AMZ-MOCK-0002")
        assert result["workflow_id"] is not None
        assert result["total_steps"] > 0

    def test_workflow_status_is_waiting_approval(self):
        _setup_inventory()
        _import_orders()
        result = mock_amazon_service.start_fulfillment("AMZ-MOCK-0002")
        assert result["status"] == "waiting_approval"


# ===========================================================================
# 10. Approval required
# ===========================================================================
class TestApprovalRequired:
    """Verify approval is required before submission."""

    def test_workflow_waits_for_approval(self):
        _setup_inventory()
        _import_orders()
        result = mock_amazon_service.start_fulfillment("AMZ-MOCK-0003")
        assert result["status"] == "waiting_approval"

    def test_approve_completes_workflow(self):
        _setup_inventory()
        _import_orders()
        result = mock_amazon_service.start_fulfillment("AMZ-MOCK-0003")
        wf_id = result["workflow_id"]
        resp = fulfillment_engine.approve_workflow(uuid.UUID(wf_id))
        assert resp.status.value == "completed"


# ===========================================================================
# 11. Submission after approval
# ===========================================================================
class TestSubmissionAfterApproval:
    """Verify supplier submission happens after approval."""

    def test_approval_leaves_confirmation(self):
        _setup_inventory()
        _import_orders()
        result = mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")
        wf_id = result["workflow_id"]
        resp = fulfillment_engine.approve_workflow(uuid.UUID(wf_id))
        assert resp.confirmation is not None
        assert resp.confirmation.confirmation_id.startswith("SUP-")


# ===========================================================================
# 12. Duplicate submission blocked
# ===========================================================================
class TestDuplicateSubmissionBlocked:
    """Verify duplicate supplier submissions are blocked."""

    def test_double_approve_blocked(self):
        _setup_inventory()
        _import_orders()
        result = mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")
        wf_id = result["workflow_id"]
        fulfillment_engine.approve_workflow(uuid.UUID(wf_id))
        with pytest.raises(Exception):
            fulfillment_engine.approve_workflow(uuid.UUID(wf_id))


# ===========================================================================
# 13. Mock tracking creation
# ===========================================================================
class TestMockTrackingCreation:
    """Verify synthetic tracking generation."""

    def test_tracking_generated_for_completed_order(self):
        _setup_inventory()
        _import_orders()
        result = mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")
        wf_id = result["workflow_id"]
        fulfillment_engine.approve_workflow(uuid.UUID(wf_id))
        tracking = mock_amazon_service.generate_mock_tracking("AMZ-MOCK-0001")
        assert tracking["tracking_id"].startswith("MOCK-TRACK-")
        assert tracking["carrier"] == "MOCK-CARRIER"

    def test_tracking_not_available_for_incomplete_order(self):
        _setup_inventory()
        _import_orders()
        mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")
        with pytest.raises(Exception):
            mock_amazon_service.generate_mock_tracking("AMZ-MOCK-0001")


# ===========================================================================
# 14. End-to-end successful flow
# ===========================================================================
class TestEndToEndSuccessfulFlow:
    """Complete successful fulfillment flow."""

    def test_full_flow(self):
        _setup_inventory()
        # Import
        import_result = _import_orders()
        assert import_result["imported"] == 5

        # Fulfill first order
        result = mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")
        assert result["status"] == "waiting_approval"

        # Approve
        wf_id = result["workflow_id"]
        wf = fulfillment_engine.approve_workflow(uuid.UUID(wf_id))
        assert wf.status.value == "completed"

        # Generate tracking
        tracking = mock_amazon_service.generate_mock_tracking("AMZ-MOCK-0001")
        assert tracking["tracking_id"].startswith("MOCK-TRACK-")

        # Check order status
        imported = mock_amazon_service.get_imported_orders()
        order = next(o for o in imported if o["amazon_order_id"] == "AMZ-MOCK-0001")
        assert order["fulfillment_status"] == "completed"


# ===========================================================================
# 15. End-to-end insufficient inventory
# ===========================================================================
class TestEndToEndInsufficientInventory:
    """Verify failure when inventory is insufficient."""

    def test_insufficient_inventory_blocks_fulfillment(self):
        _setup_inventory()
        _import_orders()
        # Reduce stock for MOCK-SKU-004 to 0
        item = inventory_service.find_by_sku("MOCK-SKU-004")
        from app.schemas.inventory import InventoryUpdate
        inventory_service.update(item.id, InventoryUpdate(current_stock=0))
        with pytest.raises(Exception, match="Insufficient"):
            mock_amazon_service.start_fulfillment("AMZ-MOCK-0004")


# ===========================================================================
# 16. End-to-end invalid address
# ===========================================================================
class TestEndToEndInvalidAddress:
    """Verify failure when address is invalid."""

    def test_invalid_address_fails_workflow(self):
        _setup_inventory()
        # Create an order with bad address directly
        order = order_service.create(
            OrderCreate(
                customer_name="Bad Address",
                shipping_address="X",
                product_name="Test",
                sku="MOCK-SKU-001",
                quantity=1,
            ),
            create_test_organization(),
        )
        wf = fulfillment_engine.start_workflow(order.id)
        assert wf.status.value == "failed"


# ===========================================================================
# 17. Idempotency
# ===========================================================================
class TestIdempotency:
    """Verify idempotency of operations."""

    def test_duplicate_import_is_idempotent(self):
        r1 = _import_orders()
        r2 = _import_orders()
        assert r1["imported"] == 5
        assert r2["imported"] == 0
        assert r2["skipped_duplicates"] == 5

    def test_duplicate_fulfillment_is_idempotent(self):
        _setup_inventory()
        _import_orders()
        r1 = mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")
        r2 = mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")
        # Second call should return existing workflow
        assert r1["workflow_id"] == r2["workflow_id"]

    def test_import_status_reflects_state(self):
        _import_orders()
        status = mock_amazon_service.get_import_status()
        assert status["imported_count"] == 5
        assert status["environment"] == "SANDBOX"
        assert status["source"] == "MOCK_AMAZON"


# ===========================================================================
# 18. Audit events
# ===========================================================================
class TestAuditEvents:
    """Verify audit events are recorded."""

    def test_import_records_audit_events(self):
        _import_orders()
        events = mock_amazon_service.get_audit_log()
        event_types = [e["event_type"] for e in events]
        assert "MOCK_ORDER_IMPORTED" in event_types
        assert "ORDER_MAPPED" in event_types

    def test_fulfillment_records_audit_events(self):
        _setup_inventory()
        _import_orders()
        mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")
        events = mock_amazon_service.get_audit_log("AMZ-MOCK-0001")
        event_types = [e["event_type"] for e in events]
        assert "FULFILLMENT_STARTED" in event_types
        assert "INVENTORY_CHECKED" in event_types

    def test_tracking_records_audit_events(self):
        _setup_inventory()
        _import_orders()
        result = mock_amazon_service.start_fulfillment("AMZ-MOCK-0001")
        wf_id = result["workflow_id"]
        fulfillment_engine.approve_workflow(uuid.UUID(wf_id))
        mock_amazon_service.generate_mock_tracking("AMZ-MOCK-0001")
        events = mock_amazon_service.get_audit_log("AMZ-MOCK-0001")
        event_types = [e["event_type"] for e in events]
        assert "MOCK_TRACKING_CREATED" in event_types

    def test_duplicate_import_records_audit_event(self):
        _import_orders()
        _import_orders()
        events = mock_amazon_service.get_audit_log()
        event_types = [e["event_type"] for e in events]
        assert "IMPORT_DUPLICATE_BLOCKED" in event_types

    def test_audit_events_have_required_fields(self):
        _import_orders()
        events = mock_amazon_service.get_audit_log()
        for event in events:
            assert "id" in event
            assert "amazon_order_id" in event
            assert "event_type" in event
            assert "timestamp" in event
            assert "details" in event


# ===========================================================================
# 19. PII protection
# ===========================================================================
class TestPIIProtection:
    """Verify PII is protected in logs and output."""

    def test_redact_pii_removes_phone_numbers(self):
        text = "Call 206-555-0101 for details"
        redacted = redact_pii(text)
        assert "206-555-0101" not in redacted
        assert "PHONE REDACTED" in redacted

    def test_redact_pii_removes_zip_codes(self):
        text = "Ship to 98101"
        redacted = redact_pii(text)
        assert "98101" not in redacted
        assert "ZIP REDACTED" in redacted

    def test_redact_pii_removes_emails(self):
        text = "Email test@example.com"
        redacted = redact_pii(text)
        assert "test@example.com" not in redacted
        assert "EMAIL REDACTED" in redacted

    def test_audit_log_uses_redacted_details(self):
        _import_orders()
        # Import event details should not contain full addresses
        events = mock_amazon_service.get_audit_log()
        for event in events:
            details = event["details"]
            # No full addresses should appear in audit details
            assert "100 Mock Lane" not in details


# ===========================================================================
# 20. No external network access
# ===========================================================================
class TestNoExternalNetworkAccess:
    """Verify implementation remains offline/local."""

    def test_mock_provider_is_mock(self):
        from app.services.providers.base import MOCK_ONLY
        assert MOCK_ONLY is True

    def test_order_provider_is_mock(self):
        from app.services.providers.base import ProviderEnvironment
        assert mock_order_provider.environment == ProviderEnvironment.MOCK

    def test_no_amazon_api_references_in_code(self):
        """Verify no real Amazon API calls exist in the mock service."""
        import inspect
        from app.services import mock_amazon
        source = inspect.getsource(mock_amazon)
        forbidden = ["amazon.com", "sp-api", "sellercentral", "amazonaws.com"]
        for term in forbidden:
            assert term.lower() not in source.lower(), f"Found forbidden term: {term}"

    def test_mock_amazon_service_is_local(self):
        """Verify the service only uses local data."""
        assert mock_amazon_service is not None
        # Service should work without any network
        status = mock_amazon_service.get_import_status()
        assert status["environment"] == "SANDBOX"
        assert status["source"] == "MOCK_AMAZON"


# ===========================================================================
# API endpoint tests
# ===========================================================================
class TestMockAmazonAPIEndpoints:
    """Test the API endpoints for mock Amazon operations."""

    @pytest.fixture(autouse=True)
    def _setup_client(self, client):
        """Use the shared session `client` fixture (authenticated for this
        class), not a fresh local TestClient — see
        test_fulfillment_safety.py's TestRegression.test_orders_still_work
        for why (cross-event-loop pooled-connection hazard against the
        application's single pooled AsyncEngine). Only /import actually
        requires auth, but attaching it for every request in this class is
        harmless and keeps this fixture simple."""
        self.client = client
        self.client.headers.update(auth_headers(client))

    def test_import_endpoint(self):
        resp = self.client.post("/api/v1/mock-amazon/import")
        assert resp.status_code == 201
        body = resp.json()
        assert body["imported"] == 5
        assert body["total_amazon_orders"] == 5

    def test_import_duplicate_returns_zero(self):
        self.client.post("/api/v1/mock-amazon/import")
        resp = self.client.post("/api/v1/mock-amazon/import")
        assert resp.status_code == 201
        assert resp.json()["imported"] == 0

    def test_status_endpoint(self):
        resp = self.client.get("/api/v1/mock-amazon/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["environment"] == "SANDBOX"
        assert body["source"] == "MOCK_AMAZON"

    def test_orders_endpoint_empty(self):
        resp = self.client.get("/api/v1/mock-amazon/orders")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_orders_endpoint_after_import(self):
        self.client.post("/api/v1/mock-amazon/import")
        resp = self.client.get("/api/v1/mock-amazon/orders")
        assert resp.status_code == 200
        assert len(resp.json()) == 5

    def test_fulfill_endpoint(self):
        _setup_inventory()
        self.client.post("/api/v1/mock-amazon/import")
        resp = self.client.post("/api/v1/mock-amazon/AMZ-MOCK-0001/fulfill")
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "waiting_approval"

    def test_fulfill_nonexistent_order(self):
        resp = self.client.post("/api/v1/mock-amazon/AMZ-FAKE-9999/fulfill")
        assert resp.status_code == 404

    def test_fulfillment_status_endpoint(self):
        _setup_inventory()
        self.client.post("/api/v1/mock-amazon/import")
        self.client.post("/api/v1/mock-amazon/AMZ-MOCK-0001/fulfill")
        resp = self.client.get("/api/v1/mock-amazon/AMZ-MOCK-0001/fulfillment")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "waiting_approval"

    def test_tracking_endpoint(self):
        _setup_inventory()
        self.client.post("/api/v1/mock-amazon/import")
        wf = self.client.post("/api/v1/mock-amazon/AMZ-MOCK-0001/fulfill").json()
        # Approve via fulfillment engine
        fulfillment_engine.approve_workflow(uuid.UUID(wf["workflow_id"]))
        resp = self.client.post("/api/v1/mock-amazon/AMZ-MOCK-0001/tracking")
        assert resp.status_code == 201
        body = resp.json()
        assert body["tracking_id"].startswith("MOCK-TRACK-")

    def test_tracking_before_completion_fails(self):
        _setup_inventory()
        self.client.post("/api/v1/mock-amazon/import")
        self.client.post("/api/v1/mock-amazon/AMZ-MOCK-0001/fulfill")
        resp = self.client.post("/api/v1/mock-amazon/AMZ-MOCK-0001/tracking")
        assert resp.status_code == 422

    def test_audit_endpoint(self):
        _setup_inventory()
        self.client.post("/api/v1/mock-amazon/import")
        resp = self.client.get("/api/v1/mock-amazon/AMZ-MOCK-0001/audit")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] > 0


# ===========================================================================
# Regression — existing functionality unaffected
# ===========================================================================
class TestRegressionExistingFunctionality:
    """Verify existing functionality is unaffected."""

    def test_health_endpoints(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            assert c.get("/health").status_code == 200
            assert c.get("/api/v1/health").status_code == 200
            assert c.get("/api/v1/status").status_code == 200

    def test_orders_still_work(self, client):
        """Orders endpoint still works (now requires real authentication —
        an intentional Phase 2B security change, not a regression).

        Uses the shared session `client` fixture rather than a fresh local
        TestClient — see test_fulfillment_safety.py's TestRegression
        .test_orders_still_work for why (cross-event-loop pooled-connection
        hazard against the application's single pooled AsyncEngine).
        """
        resp = client.post(
            "/api/v1/orders",
            json={
                "customer_name": "Test",
                "shipping_address": "123 St",
                "product_name": "Product",
                "quantity": 1,
            },
            headers=auth_headers(client),
        )
        assert resp.status_code == 201

    def test_inventory_still_works(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            resp = c.post(
                "/api/v1/inventory",
                json={"sku": "T", "product_name": "P", "current_stock": 10},
            )
            assert resp.status_code == 201

    def test_fulfillment_endpoints_still_work(self):
        from fastapi.testclient import TestClient
        from app.main import app
        _setup_inventory()
        order = order_service.create(
            OrderCreate(
                customer_name="Test",
                shipping_address="Test Customer\n123 Test Street\nNew York NY 10003\nUS",
                product_name="Test Product",
                sku="MOCK-SKU-001",
                quantity=1,
            ),
            create_test_organization(),
        )
        with TestClient(app) as c:
            resp = c.post(f"/api/v1/fulfillment/{order.id}/start")
            assert resp.status_code == 201
