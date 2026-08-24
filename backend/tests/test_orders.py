"""Tests for the generic Order API endpoints.

Covers POST, GET list (paginated + filtered), GET by ID, PATCH —
plus 404, validation errors, transition validation,
pagination edge cases, and regression checks.
"""

import uuid

import pytest

from app.services.order_service import order_service


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_order_service():
    """Clear in-memory store before every test so tests are independent."""
    order_service.clear()
    yield
    order_service.clear()


ORDER_PAYLOAD = {
    "customer_name": "Jane Doe",
    "shipping_address": "123 Main St, Springfield, IL 62701",
    "product_name": "Wireless Mouse",
    "quantity": 2,
}


def _create_order(client, **overrides):
    """Helper: create an order and return the response JSON."""
    payload = {**ORDER_PAYLOAD, **overrides}
    return client.post("/api/v1/orders", json=payload).json()


# ===========================================================================
# POST /api/v1/orders
# ===========================================================================

class TestCreateOrder:
    """POST /api/v1/orders"""

    def test_create_order(self, client):
        resp = client.post("/api/v1/orders", json=ORDER_PAYLOAD)
        assert resp.status_code == 201
        body = resp.json()
        assert body["customer_name"] == "Jane Doe"
        assert body["shipping_address"] == ORDER_PAYLOAD["shipping_address"]
        assert body["product_name"] == "Wireless Mouse"
        assert body["quantity"] == 2
        assert body["status"] == "pending"
        assert "id" in body
        assert "created_at" in body
        assert "updated_at" in body

    def test_create_order_default_status_pending(self, client):
        resp = client.post("/api/v1/orders", json=ORDER_PAYLOAD)
        assert resp.json()["status"] == "pending"

    def test_create_order_explicit_processing(self, client):
        payload = {**ORDER_PAYLOAD, "status": "processing"}
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 201
        assert resp.json()["status"] == "processing"

    @pytest.mark.parametrize("bad_status", ["unknown", "PENDING", "done", "shipped "])
    def test_create_invalid_status_returns_422(self, client, bad_status):
        payload = {**ORDER_PAYLOAD, "status": bad_status}
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 422

    def test_create_missing_customer_name_returns_422(self, client):
        payload = {**ORDER_PAYLOAD, "customer_name": ""}
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 422

    def test_create_missing_shipping_address_returns_422(self, client):
        payload = {**ORDER_PAYLOAD, "shipping_address": ""}
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 422

    def test_create_missing_product_name_returns_422(self, client):
        payload = {**ORDER_PAYLOAD, "product_name": ""}
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 422

    def test_create_quantity_zero_returns_422(self, client):
        payload = {**ORDER_PAYLOAD, "quantity": 0}
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 422

    def test_create_quantity_negative_returns_422(self, client):
        payload = {**ORDER_PAYLOAD, "quantity": -1}
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 422

    def test_create_returns_unique_id(self, client):
        r1 = client.post("/api/v1/orders", json=ORDER_PAYLOAD).json()
        r2 = client.post("/api/v1/orders", json=ORDER_PAYLOAD).json()
        assert r1["id"] != r2["id"]


# ===========================================================================
# GET /api/v1/orders  (paginated)
# ===========================================================================

class TestListOrders:
    """GET /api/v1/orders — paginated response."""

    def test_empty_list_returns_paginated_response(self, client):
        resp = client.get("/api/v1/orders")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["page"] == 1
        assert body["page_size"] == 10
        assert body["total_items"] == 0
        assert body["total_pages"] == 0

    def test_returns_created_orders_in_items(self, client):
        _create_order(client, customer_name="Alice")
        _create_order(client, customer_name="Bob")
        resp = client.get("/api/v1/orders")
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total_items"] == 2

    def test_list_preserves_insertion_order(self, client):
        r1 = _create_order(client, customer_name="First")
        r2 = _create_order(client, customer_name="Second")
        items = client.get("/api/v1/orders").json()["items"]
        assert items[0]["id"] == r1["id"]
        assert items[1]["id"] == r2["id"]

    def test_response_is_paginated_type(self, client):
        resp = client.get("/api/v1/orders")
        body = resp.json()
        assert isinstance(body["items"], list)
        assert isinstance(body["page"], int)
        assert isinstance(body["page_size"], int)
        assert isinstance(body["total_items"], int)
        assert isinstance(body["total_pages"], int)

    def test_page_2_returns_second_slice(self, client):
        for i in range(15):
            _create_order(client, customer_name=f"Customer {i}")
        resp = client.get("/api/v1/orders?page=2&page_size=10").json()
        assert len(resp["items"]) == 5
        assert resp["page"] == 2

    def test_page_beyond_total_returns_empty_items(self, client):
        _create_order(client)
        resp = client.get("/api/v1/orders?page=99&page_size=10").json()
        assert resp["items"] == []
        assert resp["total_items"] == 1

    def test_total_pages_calculation(self, client):
        for i in range(25):
            _create_order(client, customer_name=f"Customer {i}")
        resp = client.get("/api/v1/orders?page_size=10").json()
        assert resp["total_pages"] == 3

    def test_page_0_returns_422(self, client):
        resp = client.get("/api/v1/orders?page=0")
        assert resp.status_code == 422

    def test_negative_page_returns_422(self, client):
        resp = client.get("/api/v1/orders?page=-1")
        assert resp.status_code == 422

    def test_page_size_0_returns_422(self, client):
        resp = client.get("/api/v1/orders?page_size=0")
        assert resp.status_code == 422

    def test_large_page_size_caps_at_100(self, client):
        resp = client.get("/api/v1/orders?page_size=101")
        assert resp.status_code == 422


# ===========================================================================
# GET /api/v1/orders/{order_id}
# ===========================================================================

class TestGetOrder:
    """GET /api/v1/orders/{order_id}"""

    def test_get_existing_order(self, client):
        created = _create_order(client)
        resp = client.get(f"/api/v1/orders/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_missing_order_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/orders/{fake_id}")
        assert resp.status_code == 404

    def test_get_404_body_has_error_key(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/orders/{fake_id}")
        assert "error" in resp.json()

    def test_get_returns_correct_fields(self, client):
        created = _create_order(client)
        resp = client.get(f"/api/v1/orders/{created['id']}").json()
        assert set(resp.keys()) == {
            "id", "customer_name", "shipping_address", "product_name",
            "quantity", "status", "created_at", "updated_at",
        }
        assert resp["customer_name"] == "Jane Doe"
        assert resp["quantity"] == 2


# ===========================================================================
# PATCH /api/v1/orders/{order_id}
# ===========================================================================

class TestUpdateOrder:
    """PATCH /api/v1/orders/{order_id}"""

    def test_update_status_pending_to_processing(self, client):
        created = _create_order(client)
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "processing"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"

    def test_update_status_processing_to_shipped(self, client):
        created = _create_order(client, status="processing")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "shipped"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "shipped"

    def test_update_status_to_delivered(self, client):
        created = _create_order(client, status="shipped")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "delivered"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"

    def test_update_status_to_cancelled(self, client):
        created = _create_order(client)
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_from_processing(self, client):
        created = _create_order(client, status="processing")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_from_shipped(self, client):
        created = _create_order(client, status="shipped")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_update_updates_timestamp(self, client):
        created = _create_order(client)
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "processing"},
        )
        assert resp.json()["updated_at"] >= created["updated_at"]

    def test_update_missing_order_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.patch(f"/api/v1/orders/{fake_id}", json={"status": "shipped"})
        assert resp.status_code == 404

    def test_update_without_status_field_returns_422(self, client):
        created = _create_order(client)
        resp = client.patch(f"/api/v1/orders/{created['id']}", json={})
        assert resp.status_code == 422

    @pytest.mark.parametrize("bad_status", ["unknown", "PENDING", "done", "cancelled "])
    def test_update_invalid_status_returns_422(self, client, bad_status):
        created = _create_order(client)
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": bad_status},
        )
        assert resp.status_code == 422


# ===========================================================================
# Transition validation
# ===========================================================================

class TestTransitionValidation:
    """Ensure invalid status transitions are rejected."""

    def test_delivered_to_pending_rejected(self, client):
        created = _create_order(client, status="delivered")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "pending"},
        )
        assert resp.status_code == 422
        assert "error" in resp.json()

    def test_delivered_to_processing_rejected(self, client):
        created = _create_order(client, status="delivered")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "processing"},
        )
        assert resp.status_code == 422

    def test_cancelled_to_shipped_rejected(self, client):
        created = _create_order(client, status="cancelled")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "shipped"},
        )
        assert resp.status_code == 422

    def test_cancelled_to_pending_rejected(self, client):
        created = _create_order(client, status="cancelled")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "pending"},
        )
        assert resp.status_code == 422

    def test_shipped_to_pending_rejected(self, client):
        created = _create_order(client, status="shipped")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "pending"},
        )
        assert resp.status_code == 422

    def test_shipped_to_processing_rejected(self, client):
        created = _create_order(client, status="shipped")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "processing"},
        )
        assert resp.status_code == 422

    def test_processing_to_pending_rejected(self, client):
        created = _create_order(client, status="processing")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "pending"},
        )
        assert resp.status_code == 422

    # --- valid forward transitions ---

    def test_pending_to_processing_valid(self, client):
        created = _create_order(client)
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "processing"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"

    def test_processing_to_shipped_valid(self, client):
        created = _create_order(client, status="processing")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "shipped"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "shipped"

    def test_shipped_to_delivered_valid(self, client):
        created = _create_order(client, status="shipped")
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "delivered"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"


# ===========================================================================
# Status filtering
# ===========================================================================

class TestFilterByStatus:
    """GET /api/v1/orders?status=... filtering."""

    def test_filter_pending(self, client):
        _create_order(client, customer_name="A")
        _create_order(client, customer_name="B", status="processing")
        resp = client.get("/api/v1/orders?status=pending").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["customer_name"] == "A"

    def test_filter_processing(self, client):
        _create_order(client, status="processing")
        _create_order(client, status="shipped")
        resp = client.get("/api/v1/orders?status=processing").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["status"] == "processing"

    def test_filter_no_match(self, client):
        _create_order(client)
        resp = client.get("/api/v1/orders?status=delivered").json()
        assert resp["items"] == []
        assert resp["total_items"] == 0

    def test_filter_invalid_status_returns_422(self, client):
        resp = client.get("/api/v1/orders?status=bogus")
        assert resp.status_code == 422

    def test_no_filter_returns_all(self, client):
        _create_order(client, status="pending")
        _create_order(client, status="processing")
        _create_order(client, status="shipped")
        resp = client.get("/api/v1/orders").json()
        assert resp["total_items"] == 3


# ===========================================================================
# Regression — existing routes still work
# ===========================================================================

class TestRegressionExistingRoutes:
    """Ensure health / status routes are unaffected by order routes."""

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
