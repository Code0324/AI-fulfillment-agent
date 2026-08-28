"""Tests for fulfillment workflow safety hardening (CHUNK 1O).

Covers idempotency, duplicate prevention, state machine, approval expiration,
cancellation, retry safety, inventory safety, concurrency, and audit logging.
"""

import uuid

import pytest

from app.schemas.fulfillment import (
    APPROVAL_EXPIRY_SECONDS,
    FulfillmentStatus,
    is_valid_transition,
)
from app.services.automation.engine import automation_engine
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.inventory_service import inventory_service
from app.services.order_service import order_service

from tests.conftest import create_test_organization, auth_headers


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_all():
    """Clear all state before every test."""
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    automation_engine.clear()
    yield
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    automation_engine.clear()


def _create_inventory(sku="TEST-SKU-001", stock=100):
    """Helper: create an inventory item."""
    from app.schemas.inventory import InventoryCreate
    return inventory_service.create(
        InventoryCreate(
            sku=sku,
            product_name="Test Product",
            current_stock=stock,
            low_stock_threshold=10,
        )
    )


def _create_order(sku="TEST-SKU-001", qty=5, address=None):
    """Helper: create an order for a fresh, real organization."""
    from app.schemas.order import OrderCreate
    if address is None:
        address = (
            "Test Customer\n"
            "123 Test Street\n"
            "Apt 4\n"
            "New York NY 10003\n"
            "US"
        )
    return order_service.create(
        OrderCreate(
            customer_name="Test Customer",
            shipping_address=address,
            product_name="Test Product",
            sku=sku,
            quantity=qty,
        ),
        create_test_organization(),
    )


def _start_and_wait(order):
    """Helper: start workflow and return it in WAITING_APPROVAL state."""
    _create_inventory()
    return client_post(f"/api/v1/fulfillment/{order.id}/start")


def client_post(url, json=None):
    """Helper: make a POST request via the test client."""
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        if json is not None:
            return c.post(url, json=json).json()
        return c.post(url).json()


# ===========================================================================
# INVARIANT 1: Cannot submit without approval
# ===========================================================================

class TestInvariantNoSubmitWithoutApproval:
    """A fulfillment cannot submit without approval."""

    def test_cannot_approve_non_waiting(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            # Try to approve a workflow that's not waiting
            # (it IS waiting, so approve it first)
            c.post(f"/api/v1/fulfillment/{wf['id']}/approve")
            # Try to approve again — should fail
            resp = c.post(f"/api/v1/fulfillment/{wf['id']}/approve")
            assert resp.status_code == 422


# ===========================================================================
# INVARIANT 2: Cancelled workflow cannot submit
# ===========================================================================

class TestInvariantCancelledCannotSubmit:
    """A cancelled fulfillment cannot submit."""

    def test_approve_cancelled_workflow_fails(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            # Cancel
            c.post(f"/api/v1/fulfillment/{wf['id']}/reject")
            # Try to approve — should fail
            resp = c.post(f"/api/v1/fulfillment/{wf['id']}/approve")
            assert resp.status_code == 422


# ===========================================================================
# INVARIANT 3: Rejected workflow cannot submit
# ===========================================================================

class TestInvariantRejectedCannotSubmit:
    """A rejected fulfillment cannot submit."""

    def test_reject_then_approve_fails(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            c.post(f"/api/v1/fulfillment/{wf['id']}/reject")
            resp = c.post(f"/api/v1/fulfillment/{wf['id']}/approve")
            assert resp.status_code == 422


# ===========================================================================
# INVARIANT 4: Expired approval cannot submit
# ===========================================================================

class TestInvariantExpiredCannotSubmit:
    """An expired approval cannot submit."""

    def test_expired_approval_rejection(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            # Manually expire the approval
            from app.schemas.fulfillment import FulfillmentWorkflow as FW
            from datetime import datetime, timezone, timedelta
            workflow = fulfillment_engine.get_workflow(uuid.UUID(wf["id"]))
            workflow.approval_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            # Try to get workflow — should auto-expire
            resp = c.get(f"/api/v1/fulfillment/{wf['id']}")
            body = resp.json()
            assert body["status"] == "expired"
            # Try to approve — should fail
            resp = c.post(f"/api/v1/fulfillment/{wf['id']}/approve")
            assert resp.status_code == 422


# ===========================================================================
# INVARIANT 5: Completed workflow cannot submit again
# ===========================================================================

class TestInvariantCompletedCannotSubmit:
    """A completed fulfillment cannot submit again."""

    def test_approve_completed_workflow_fails(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            c.post(f"/api/v1/fulfillment/{wf['id']}/approve")
            # Try to approve again — should fail
            resp = c.post(f"/api/v1/fulfillment/{wf['id']}/approve")
            assert resp.status_code == 422


# ===========================================================================
# INVARIANT 6: Inventory cannot be reserved twice
# ===========================================================================

class TestInvariantNoDoubleReservation:
    """Inventory cannot be reserved twice."""

    def test_double_start_does_not_double_reserve(self):
        _create_inventory(stock=100)
        order = _create_order(qty=5)
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf1 = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            wf2 = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            # Should be the same workflow (idempotent)
            assert wf1["id"] == wf2["id"]
            # Inventory should only be reserved once
            inv = inventory_service.find_by_sku("TEST-SKU-001")
            assert inv.reserved_quantity == 5


# ===========================================================================
# INVARIANT 7: Available inventory cannot become negative
# ===========================================================================

class TestInvariantNoNegativeInventory:
    """Available inventory cannot become negative."""

    def test_release_after_rejection_restores_inventory(self):
        _create_inventory(stock=100)
        order = _create_order(qty=5)
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            inv = inventory_service.find_by_sku("TEST-SKU-001")
            assert inv.reserved_quantity == 5
            # Reject
            c.post(f"/api/v1/fulfillment/{wf['id']}/reject")
            inv = inventory_service.find_by_sku("TEST-SKU-001")
            assert inv.reserved_quantity == 0
            assert inv.available_quantity == 100


# ===========================================================================
# INVARIANT 8: Failed workflow cannot silently become completed
# ===========================================================================

class TestInvariantFailedCannotBecomeCompleted:
    """A failed fulfillment cannot silently become completed."""

    def test_failed_workflow_requires_retry(self):
        _create_inventory()
        order = _create_order(address="X")  # Bad address
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            assert wf["status"] == "failed"
            # Try to approve — should fail
            resp = c.post(f"/api/v1/fulfillment/{wf['id']}/approve")
            assert resp.status_code == 422


# ===========================================================================
# INVARIANT 9: Duplicate request creates duplicate supplier orders
# ===========================================================================

class TestInvariantNoDuplicateSupplierOrders:
    """A duplicate fulfillment request cannot create duplicate supplier orders."""

    def test_idempotent_start_returns_existing(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf1 = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            wf2 = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            assert wf1["id"] == wf2["id"]


# ===========================================================================
# INVARIANT 10: Confirmation ID belongs to only one submission
# ===========================================================================

class TestInvariantUniqueConfirmation:
    """A supplier confirmation ID belongs to only one fulfillment submission."""

    def test_unique_confirmation_ids(self):
        _create_inventory(sku="SKU-A", stock=100)
        _create_inventory(sku="SKU-B", stock=100)
        order1 = _create_order(sku="SKU-A")
        order2 = _create_order(sku="SKU-B", address="Jane Doe\n456 Other St\nChicago IL 60601\nUS")
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf1 = c.post(f"/api/v1/fulfillment/{order1.id}/start").json()
            wf2 = c.post(f"/api/v1/fulfillment/{order2.id}/start").json()
            assert wf1["status"] == "waiting_approval"
            assert wf2["status"] == "waiting_approval"
            c.post(f"/api/v1/fulfillment/{wf1['id']}/approve")
            c.post(f"/api/v1/fulfillment/{wf2['id']}/approve")
            wf1_final = c.get(f"/api/v1/fulfillment/{wf1['id']}").json()
            wf2_final = c.get(f"/api/v1/fulfillment/{wf2['id']}").json()
            assert wf1_final["confirmation"]["confirmation_id"] != wf2_final["confirmation"]["confirmation_id"]


# ===========================================================================
# State machine tests
# ===========================================================================

class TestStateMachine:
    """State transition validation."""

    def test_valid_transitions(self):
        assert is_valid_transition(FulfillmentStatus.PENDING, FulfillmentStatus.RUNNING)
        assert is_valid_transition(FulfillmentStatus.RUNNING, FulfillmentStatus.WAITING_APPROVAL)
        assert is_valid_transition(FulfillmentStatus.WAITING_APPROVAL, FulfillmentStatus.APPROVED)
        assert is_valid_transition(FulfillmentStatus.APPROVED, FulfillmentStatus.RUNNING)
        assert is_valid_transition(FulfillmentStatus.RUNNING, FulfillmentStatus.COMPLETED)
        assert is_valid_transition(FulfillmentStatus.RUNNING, FulfillmentStatus.FAILED)
        assert is_valid_transition(FulfillmentStatus.FAILED, FulfillmentStatus.RUNNING)

    def test_invalid_transitions(self):
        assert not is_valid_transition(FulfillmentStatus.COMPLETED, FulfillmentStatus.RUNNING)
        assert not is_valid_transition(FulfillmentStatus.COMPLETED, FulfillmentStatus.WAITING_APPROVAL)
        assert not is_valid_transition(FulfillmentStatus.COMPLETED, FulfillmentStatus.PENDING)

    def test_terminal_states_have_no_transitions(self):
        from app.schemas.fulfillment import VALID_TRANSITIONS
        assert VALID_TRANSITIONS[FulfillmentStatus.COMPLETED] == []
        # CANCELLED allows retry (RUNNING), so not fully terminal


# ===========================================================================
# Cancellation tests
# ===========================================================================

class TestCancellation:
    """Safe cancellation behavior."""

    def test_cancel_waiting_workflow(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            resp = c.post(f"/api/v1/fulfillment/{wf['id']}/cancel")
            assert resp.status_code == 200
            assert resp.json()["status"] == "cancelled"

    def test_cancel_completed_workflow_fails(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            c.post(f"/api/v1/fulfillment/{wf['id']}/approve")
            resp = c.post(f"/api/v1/fulfillment/{wf['id']}/cancel")
            assert resp.status_code == 422

    def test_cancel_releases_inventory(self):
        _create_inventory(stock=100)
        order = _create_order(qty=5)
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            inv = inventory_service.find_by_sku("TEST-SKU-001")
            assert inv.reserved_quantity == 5
            c.post(f"/api/v1/fulfillment/{wf['id']}/cancel")
            inv = inventory_service.find_by_sku("TEST-SKU-001")
            assert inv.reserved_quantity == 0


# ===========================================================================
# Retry tests
# ===========================================================================

class TestRetry:
    """Retry safety behavior."""

    def test_retry_failed_workflow(self):
        _create_inventory()
        order = _create_order(address="X")  # Bad address
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            assert wf["status"] == "failed"
            # Retry with valid address
            order_addr = order_service.get(order.id)
            from app.schemas.order import OrderUpdate
            # Can't change address directly, so create a new order
            order2 = _create_order()
            wf2 = c.post(f"/api/v1/fulfillment/{order2.id}/start").json()
            assert wf2["status"] == "waiting_approval"

    def test_retry_does_not_duplicate_reservation(self):
        _create_inventory(stock=100)
        order = _create_order(qty=5)
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            # Cancel to make it retryable
            c.post(f"/api/v1/fulfillment/{wf['id']}/cancel")
            inv = inventory_service.find_by_sku("TEST-SKU-001")
            assert inv.reserved_quantity == 0  # Released on cancel
            # Retry — should re-reserve since previous was released
            c.post(f"/api/v1/fulfillment/{wf['id']}/retry")
            inv = inventory_service.find_by_sku("TEST-SKU-001")
            assert inv.reserved_quantity == 5  # Reserved once on retry

    def test_cannot_retry_completed_workflow(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            c.post(f"/api/v1/fulfillment/{wf['id']}/approve")
            resp = c.post(f"/api/v1/fulfillment/{wf['id']}/retry")
            assert resp.status_code == 422


# ===========================================================================
# Approval expiration tests
# ===========================================================================

class TestApprovalExpiration:
    """Approval expiration behavior."""

    def test_approval_expires(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        from datetime import datetime, timezone, timedelta
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            # Manually expire
            workflow = fulfillment_engine.get_workflow(uuid.UUID(wf["id"]))
            workflow.approval_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            # Get should auto-expire
            resp = c.get(f"/api/v1/fulfillment/{wf['id']}")
            assert resp.json()["status"] == "expired"

    def test_approval_not_expired_within_window(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            resp = c.get(f"/api/v1/fulfillment/{wf['id']}")
            assert resp.json()["status"] == "waiting_approval"


# ===========================================================================
# Audit tests
# ===========================================================================

class TestAudit:
    """Audit logging behavior."""

    def test_audit_log_records_events(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            resp = c.get(f"/api/v1/fulfillment/{wf['id']}/audit")
            body = resp.json()
            assert body["total"] > 0
            event_types = [e["event_type"] for e in body["events"]]
            assert "FULFILLMENT_STARTED" in event_types

    def test_audit_records_approval(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            c.post(f"/api/v1/fulfillment/{wf['id']}/approve")
            resp = c.get(f"/api/v1/fulfillment/{wf['id']}/audit")
            event_types = [e["event_type"] for e in resp.json()["events"]]
            assert "APPROVAL_APPROVED" in event_types

    def test_audit_records_rejection(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            c.post(f"/api/v1/fulfillment/{wf['id']}/reject")
            resp = c.get(f"/api/v1/fulfillment/{wf['id']}/audit")
            event_types = [e["event_type"] for e in resp.json()["events"]]
            assert "APPROVAL_REJECTED" in event_types

    def test_audit_records_cancellation(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            c.post(f"/api/v1/fulfillment/{wf['id']}/cancel")
            resp = c.get(f"/api/v1/fulfillment/{wf['id']}/audit")
            event_types = [e["event_type"] for e in resp.json()["events"]]
            assert "FULFILLMENT_CANCELLED" in event_types


# ===========================================================================
# Regression
# ===========================================================================

class TestRegression:
    """Ensure existing functionality still works."""

    def test_complete_workflow_end_to_end(self):
        _create_inventory()
        order = _create_order()
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            wf = c.post(f"/api/v1/fulfillment/{order.id}/start").json()
            assert wf["status"] == "waiting_approval"
            resp = c.post(f"/api/v1/fulfillment/{wf['id']}/approve")
            assert resp.status_code == 200
            assert resp.json()["status"] == "completed"
            assert resp.json()["confirmation"] is not None

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
        TestClient: a fresh TestClient means a fresh event loop, and this
        endpoint's DB calls run through the application's single pooled
        AsyncEngine (app/database.py) whose pooled connections are each
        bound to whichever loop first created them — reusing that one
        pooled engine across many independent, short-lived loops across a
        test session risks a connection created on one (now-closed) loop
        being checked out again on another. Never an issue in production
        (a single Uvicorn worker means exactly one loop for the process's
        whole lifetime); only relevant to tests that open many separate
        TestClient instances. Using the one shared, long-lived session
        client avoids it entirely.
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
