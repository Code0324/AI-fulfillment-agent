"""Tests for the fulfillment workflow endpoints.

Covers workflow lifecycle, approval, inventory, address validation,
browser sandbox, audit, and regression.

AUTH NOTE: fulfillment.py now enforces get_current_organization +
require_permission on every route (see that module's docstring) — every
call site below authenticates via tests.conftest.auth_org()/auth_headers()
and passes the resulting Authorization header. _create_order() creates
the order under the SAME organization the returned headers belong to,
since ownership is re-verified against the database on every request.
"""

import uuid

import pytest

from app.schemas.order import OrderStatus
from app.services.automation.engine import automation_engine
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.inventory_service import inventory_service
from app.services.order_service import order_service

from tests.conftest import auth_headers, auth_org


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


def _create_order(client, sku="TEST-SKU-001", qty=5, address=None):
    """Helper: create an order for a fresh, real authenticated organization.

    Returns (order, headers) — headers authenticate a real OWNER member of
    the SAME organization the order belongs to, required now that
    fulfillment.py enforces get_current_organization + require_permission.
    """
    from app.schemas.order import OrderCreate
    if address is None:
        address = (
            "Test Customer\n"
            "123 Test Street\n"
            "Apt 4\n"
            "New York NY 10003\n"
            "US"
        )
    headers, org_id = auth_org(client)
    order = order_service.create(
        OrderCreate(
            customer_name="Test Customer",
            shipping_address=address,
            product_name="Test Product",
            sku=sku,
            quantity=qty,
        ),
        org_id,
    )
    return order, headers


# ===========================================================================
# POST /api/v1/fulfillment/{order_id}/start — Valid workflow
# ===========================================================================

class TestStartFulfillment:
    """Start a fulfillment workflow."""

    def test_start_valid_workflow(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["order_id"] == str(order.id)
        # Workflow pauses at WAITING_APPROVAL for high-risk submit
        assert body["status"] == "waiting_approval"
        # 14 steps: the original 13 plus check_price_guard (Amazon price
        # safety gate — see services/fulfillment/workflow.py).
        assert len(body["steps"]) == 14
        # Approval step should be waiting
        approval_step = next(
            s for s in body["steps"] if s["name"] == "request_approval"
        )
        assert approval_step["status"] == "waiting_approval"

    def test_start_then_approve_completes(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        assert wf["status"] == "waiting_approval"
        # Approve
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["confirmation"] is not None
        assert body["confirmation"]["confirmation_id"].startswith("SUP-")

    def test_start_with_express_shipping(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        resp = client.post(
            f"/api/v1/fulfillment/{order.id}/start",
            json={"shipping_method": "express"},
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "waiting_approval"

    def test_start_invalid_order_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/api/v1/fulfillment/{fake_id}/start", headers=auth_headers(client))
        assert resp.status_code == 404

    def test_start_requires_authentication(self, client):
        """New in this phase: fulfillment.py now enforces authentication —
        a request with no bearer token must be rejected, not routed
        through to the (unscoped, in-memory) engine."""
        _create_inventory()
        order, _headers = _create_order(client)
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start")
        assert resp.status_code in (401, 403)

    def test_start_rejects_order_from_another_organization(self, client):
        """New in this phase: an authenticated user from a DIFFERENT
        organization must not be able to start fulfillment for an order
        they don't own — it must 404, not leak existence."""
        _create_inventory()
        order, _owner_headers = _create_order(client)
        other_headers = auth_headers(client)
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=other_headers)
        assert resp.status_code == 404

    def test_start_invalid_shipping_method(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        resp = client.post(
            f"/api/v1/fulfillment/{order.id}/start",
            json={"shipping_method": "invalid"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_workflow_has_all_steps(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        step_names = [s["name"] for s in resp["steps"]]
        expected = [
            "load_order", "validate_order", "resolve_sku_mapping",
            "check_price_guard", "validate_address", "check_inventory",
            "reserve_inventory", "prepare_supplier_order",
            "select_fulfillment_provider", "prepare_provider_order",
            "validate_provider_order", "request_approval",
            "submit_fulfillment_order", "generate_confirmation",
        ]
        assert step_names == expected
        assert resp["order_source"] == "MANUAL"
        assert resp["sku_mapping_status"] == "not_required"
        assert resp["fulfillment_provider"] == "mock_sandbox_supplier"
        assert resp["provider_mode"] == "mock_sandbox"


# ===========================================================================
# Workflow — Address validation
# ===========================================================================

class TestAddressValidation:
    """Address validation in workflow."""

    def test_failed_address_stops_workflow(self, client):
        _create_inventory()
        order, headers = _create_order(client, address="X")
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers)
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
        order, headers = _create_order(client, sku="NONEXISTENT")
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "failed"

    def test_insufficient_inventory_fails(self, client):
        _create_inventory(stock=2)
        order, headers = _create_order(client, qty=10)
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "failed"

    def test_inventory_reserved_after_workflow(self, client):
        _create_inventory(stock=100)
        order, headers = _create_order(client, qty=5)
        client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
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
        order, headers = _create_order(client)
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers)
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
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["confirmation"] is not None

    def test_reject_cancels_workflow(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/reject", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "cancelled"

    def test_approve_rejects_another_organizations_workflow(self, client):
        """Approval security: an authenticated user from a different
        organization must not be able to approve someone else's workflow."""
        _create_inventory()
        order, owner_headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=owner_headers).json()
        other_headers = auth_headers(client)
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=other_headers)
        assert resp.status_code == 404
        # Confirm it genuinely did not approve — the real owner still can.
        resp2 = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=owner_headers)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "completed"


# ===========================================================================
# GET /api/v1/fulfillment — List workflows
# ===========================================================================

class TestListWorkflows:
    """List fulfillment workflows."""

    def test_empty_list(self, client):
        resp = client.get("/api/v1/fulfillment", headers=auth_headers(client))
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total_items"] == 0

    def test_list_after_start(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers)
        resp = client.get("/api/v1/fulfillment", headers=headers).json()
        assert resp["total_items"] == 1

    def test_list_is_scoped_to_organization(self, client):
        """A different organization's workflow list must not include this
        organization's workflows."""
        _create_inventory()
        order, headers = _create_order(client)
        client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers)
        other_headers = auth_headers(client)
        resp = client.get("/api/v1/fulfillment", headers=other_headers).json()
        assert resp["total_items"] == 0


# ===========================================================================
# GET /api/v1/fulfillment/{id} — Get workflow
# ===========================================================================

class TestGetWorkflow:
    """Get a single workflow."""

    def test_get_existing_workflow(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        created = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        resp = client.get(f"/api/v1/fulfillment/{created['id']}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_missing_workflow_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/fulfillment/{fake_id}", headers=auth_headers(client))
        assert resp.status_code == 404


# ===========================================================================
# POST /api/v1/fulfillment/{id}/approve — Approve
# ===========================================================================

class TestApproveRejectEdgeCases:
    """Edge cases for approve/reject."""

    def test_approve_missing_workflow_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/api/v1/fulfillment/{fake_id}/approve", headers=auth_headers(client))
        assert resp.status_code == 404

    def test_reject_missing_workflow_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/api/v1/fulfillment/{fake_id}/reject", headers=auth_headers(client))
        assert resp.status_code == 404

    def test_double_approve_fails(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
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
