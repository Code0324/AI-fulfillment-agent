"""Tests for the fulfillment workflow endpoints.

Covers workflow lifecycle, approval, inventory, address validation,
browser sandbox, audit, and regression.
"""

import uuid

import pytest

from app.schemas.order import OrderStatus
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


# ===========================================================================
# POST /api/v1/fulfillment/{order_id}/start — Valid workflow
# ===========================================================================

class TestStartFulfillment:
    """Start a fulfillment workflow."""

    def test_start_valid_workflow(self, client):
        _create_inventory()
        order = _create_order()
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start")
        assert resp.status_code == 201
        body = resp.json()
        assert body["order_id"] == str(order.id)
        # Workflow pauses at WAITING_APPROVAL for high-risk submit
        assert body["status"] == "waiting_approval"
        assert len(body["steps"]) == 13
        # Approval step should be waiting
        approval_step = next(
            s for s in body["steps"] if s["name"] == "request_approval"
        )
        assert approval_step["status"] == "waiting_approval"

    def test_start_then_approve_completes(self, client):
        _create_inventory()
        order = _create_order()
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start").json()
        assert wf["status"] == "waiting_approval"
        # Approve
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["confirmation"] is not None
        assert body["confirmation"]["confirmation_id"].startswith("SUP-")

    def test_start_with_express_shipping(self, client):
        _create_inventory()
        order = _create_order()
        resp = client.post(
            f"/api/v1/fulfillment/{order.id}/start",
            json={"shipping_method": "express"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "waiting_approval"

    def test_start_invalid_order_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/api/v1/fulfillment/{fake_id}/start")
        assert resp.status_code == 404

    def test_start_invalid_shipping_method(self, client):
        _create_inventory()
        order = _create_order()
        resp = client.post(
            f"/api/v1/fulfillment/{order.id}/start",
            json={"shipping_method": "invalid"},
        )
        assert resp.status_code == 422

    def test_workflow_has_all_steps(self, client):
        _create_inventory()
        order = _create_order()
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start").json()
        step_names = [s["name"] for s in resp["steps"]]
        expected = [
            "load_order", "validate_address", "check_inventory",
            "reserve_inventory", "prepare_supplier_order",
            "open_supplier_sandbox", "fill_product_info",
            "fill_shipping_address", "select_shipping_method",
            "verify_order", "request_approval",
            "submit_supplier_order", "generate_confirmation",
        ]
        assert step_names == expected


# ===========================================================================
# Workflow — Address validation
# ===========================================================================

class TestAddressValidation:
    """Address validation in workflow."""

    def test_failed_address_stops_workflow(self, client):
        _create_inventory()
        order = _create_order(address="X")
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start")
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "failed"
        assert "address" in body["error_message"].lower()


# ===========================================================================
# Workflow — Inventory
# ===========================================================================

class TestInventoryInWorkflow:
    """Inventory checks in workflow."""

    def test_missing_inventory_fails(self, client):
        order = _create_order(sku="NONEXISTENT")
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start")
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "failed"

    def test_insufficient_inventory_fails(self, client):
        _create_inventory(stock=2)
        order = _create_order(qty=10)
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start")
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "failed"

    def test_inventory_reserved_after_workflow(self, client):
        _create_inventory(stock=100)
        order = _create_order(qty=5)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start").json()
        # Inventory is reserved during workflow
        inv = inventory_service.find_by_sku("TEST-SKU-001")
        assert inv.reserved_quantity == 5


# ===========================================================================
# Workflow — Approval
# ===========================================================================

class TestApprovalWorkflow:
    """High-risk approval gate."""

    def test_workflow_waiting_approval(self, client):
        _create_inventory()
        order = _create_order()
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start")
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "waiting_approval"
        approval_step = next(
            (s for s in body["steps"] if s["name"] == "request_approval"), None
        )
        assert approval_step is not None
        assert approval_step["status"] == "waiting_approval"

    def test_approve_completes_workflow(self, client):
        _create_inventory()
        order = _create_order()
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start").json()
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["confirmation"] is not None

    def test_reject_cancels_workflow(self, client):
        _create_inventory()
        order = _create_order()
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start").json()
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/reject")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cancelled"


# ===========================================================================
# GET /api/v1/fulfillment — List workflows
# ===========================================================================

class TestListWorkflows:
    """List fulfillment workflows."""

    def test_empty_list(self, client):
        resp = client.get("/api/v1/fulfillment")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total_items"] == 0

    def test_list_after_start(self, client):
        _create_inventory()
        order = _create_order()
        client.post(f"/api/v1/fulfillment/{order.id}/start")
        resp = client.get("/api/v1/fulfillment").json()
        assert resp["total_items"] == 1


# ===========================================================================
# GET /api/v1/fulfillment/{id} — Get workflow
# ===========================================================================

class TestGetWorkflow:
    """Get a single workflow."""

    def test_get_existing_workflow(self, client):
        _create_inventory()
        order = _create_order()
        created = client.post(f"/api/v1/fulfillment/{order.id}/start").json()
        resp = client.get(f"/api/v1/fulfillment/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_missing_workflow_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/fulfillment/{fake_id}")
        assert resp.status_code == 404


# ===========================================================================
# POST /api/v1/fulfillment/{id}/approve — Approve
# ===========================================================================

class TestApproveRejectEdgeCases:
    """Edge cases for approve/reject."""

    def test_approve_missing_workflow_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/api/v1/fulfillment/{fake_id}/approve")
        assert resp.status_code == 404

    def test_reject_missing_workflow_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/api/v1/fulfillment/{fake_id}/reject")
        assert resp.status_code == 404

    def test_double_approve_fails(self, client):
        _create_inventory()
        order = _create_order()
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start").json()
        client.post(f"/api/v1/fulfillment/{wf['id']}/approve")
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve")
        assert resp.status_code == 422


# ===========================================================================
# Regression
# ===========================================================================

class TestRegressionExistingRoutes:
    """Ensure existing routes are unaffected."""

    def test_root_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_api_v1_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_api_v1_status(self, client):
        resp = client.get("/api/v1/status")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_tasks_still_work(self, client):
        resp = client.post("/api/v1/tasks", json={"status": "pending"})
        assert resp.status_code == 201

    def test_orders_still_work(self, client):
        """Orders endpoint still works (now requires real authentication —
        an intentional Phase 2B security change, not a regression)."""
        resp = client.post(
            "/api/v1/orders",
            json={
                "customer_name": "Test Customer",
                "shipping_address": "123 Test St",
                "product_name": "Test Product",
                "quantity": 1,
            },
            headers=auth_headers(client),
        )
        assert resp.status_code == 201

    def test_inventory_still_work(self, client):
        resp = client.post(
            "/api/v1/inventory",
            json={
                "sku": "TEST-001",
                "product_name": "Test Widget",
                "current_stock": 50,
            },
        )
        assert resp.status_code == 201

    def test_automation_still_work(self, client):
        resp = client.post("/api/v1/automation/sessions?environment=sandbox")
        assert resp.status_code == 201

    def test_address_still_work(self, client):
        resp = client.post(
            "/api/v1/address/parse",
            json={"raw_address": "John Smith\n123 Main St\nNY NY 10001\nUS"},
        )
        assert resp.status_code == 201
