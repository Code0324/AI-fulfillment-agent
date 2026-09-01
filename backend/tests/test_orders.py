"""Tests for the generic Order API endpoints.

Covers POST, GET list (paginated + filtered), GET by ID, PATCH —
plus 404, validation errors, transition validation,
pagination edge cases, inventory reservation, organization isolation,
and regression checks.

Every order endpoint requires real authentication as of Phase 2B (JWT ->
get_current_user -> get_current_organization), so every test in this file
runs against a real, freshly-signed-up user + organization via the
`_authenticate` autouse fixture below — never a default/fallback
organization, and never a bypass of authentication.
"""

import uuid

import pytest

from app.services.inventory_service import inventory_service
from app.services.order_service import order_service

from tests.conftest import auth_headers


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_services():
    """Clear all orders/inventory (across every organization) before every
    test so tests are independent. PostgreSQL-backed as of Phase 2B, but
    still fine to blanket-clear between tests: this is test cleanup, not
    production behavior."""
    order_service.clear()
    inventory_service.clear()
    yield
    order_service.clear()
    inventory_service.clear()


@pytest.fixture(autouse=True)
def _authenticate(client):
    """Sign up a fresh real user + real organization through the actual
    /auth/signup + /organizations HTTP flow, and attach a real bearer token
    to every request the shared `client` makes for the duration of this
    test. Runs after `client`'s own setup (which starts from a logged-out
    state) and before the test body, so every existing test in this file
    that calls client.post/get/patch without its own explicit
    Authorization header is still exercising the real authenticated path —
    not a bypass.
    """
    client.headers.update(auth_headers(client))


ORDER_PAYLOAD = {
    "customer_name": "Jane Doe",
    "shipping_address": "123 Main St, Springfield, IL 62701",
    "product_name": "Wireless Mouse",
    "quantity": 2,
}


def _create_order(client, headers=None, **overrides):
    """Helper: create an order and return the response JSON.

    Without an explicit `headers`, uses the client's current default
    Authorization (the organization set up by the `_authenticate` autouse
    fixture). Pass `headers` explicitly to create the order under a
    *different* organization -- see TestOrganizationIsolation.
    """
    payload = {**ORDER_PAYLOAD, **overrides}
    return client.post("/api/v1/orders", json=payload, headers=headers).json()


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

    def test_duplicate_tiktok_order_id_returns_409_not_500(self, client):
        """Regression: the DB-level UniqueConstraint on
        (organization_id, tiktok_order_id) is the real idempotency
        guarantee (see models.py). A raw IntegrityError bubbling up as an
        unhandled 500 was a real gap found during manual verification —
        this must be a clean 409, and no duplicate must be created."""
        payload = {**ORDER_PAYLOAD, "source": "TIKTOK", "tiktok_order_id": "TT-DUPCHECK-001"}
        resp1 = client.post("/api/v1/orders", json=payload)
        assert resp1.status_code == 201

        resp2 = client.post("/api/v1/orders", json={**payload, "customer_name": "Someone Else"})
        assert resp2.status_code == 409
        assert "TT-DUPCHECK-001" in resp2.json()["error"]

        listing = client.get(
            "/api/v1/orders", params={"source": "TIKTOK", "page_size": 100}
        ).json()
        matching = [o for o in listing["items"] if o.get("tiktok_order_id") == "TT-DUPCHECK-001"]
        assert len(matching) == 1


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
            "id", "organization_id", "customer_name", "shipping_address",
            "product_name", "sku", "variation", "quantity", "status",
            "source", "inventory_reserved", "tiktok_order_id", "channel_metadata",
            "sheet_synced_at", "sheet_sync_error", "sheet_sync_status", "created_at", "updated_at",
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
# Search filtering
# ===========================================================================

class TestSearchOrders:
    """GET /api/v1/orders?search=... text search."""

    def test_search_by_customer_name(self, client):
        _create_order(client, customer_name="Alice Smith")
        _create_order(client, customer_name="Bob Jones")
        resp = client.get("/api/v1/orders?search=alice").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["customer_name"] == "Alice Smith"

    def test_search_by_product_name(self, client):
        _create_order(client, product_name="Wireless Mouse")
        _create_order(client, product_name="USB Keyboard")
        resp = client.get("/api/v1/orders?search=mouse").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["product_name"] == "Wireless Mouse"

    def test_search_case_insensitive(self, client):
        _create_order(client, customer_name="Alice Smith")
        resp = client.get("/api/v1/orders?search=ALICE").json()
        assert resp["total_items"] == 1

    def test_search_partial_match(self, client):
        _create_order(client, customer_name="Alice Smith")
        _create_order(client, customer_name="Alicia Garcia")
        resp = client.get("/api/v1/orders?search=ali").json()
        assert resp["total_items"] == 2

    def test_search_no_results(self, client):
        _create_order(client, customer_name="Alice Smith")
        resp = client.get("/api/v1/orders?search=nonexistent").json()
        assert resp["total_items"] == 0
        assert resp["items"] == []

    def test_search_empty_string_returns_all(self, client):
        _create_order(client, customer_name="Alice")
        _create_order(client, customer_name="Bob")
        resp = client.get("/api/v1/orders?search=").json()
        assert resp["total_items"] == 2

    def test_search_combined_with_status_filter(self, client):
        _create_order(client, customer_name="Alice", status="pending")
        _create_order(client, customer_name="Alice", status="processing")
        _create_order(client, customer_name="Bob", status="pending")
        resp = client.get("/api/v1/orders?search=alice&status=pending").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["customer_name"] == "Alice"
        assert resp["items"][0]["status"] == "pending"

    def test_search_by_order_id_prefix(self, client):
        created = _create_order(client, customer_name="Test Order")
        order_id_prefix = created["id"][:8]
        resp = client.get(f"/api/v1/orders?search={order_id_prefix}").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["id"] == created["id"]


# ===========================================================================
# Inventory reservation integration
# ===========================================================================

class TestInventoryReservation:
    """Order ↔ Inventory reservation integration."""

    def _setup_inventory(self, client, sku="MOUSE-001", stock=50):
        """Create an inventory item and return its JSON."""
        return client.post(
            "/api/v1/inventory",
            json={"sku": sku, "product_name": "Mouse", "current_stock": stock},
        ).json()

    def test_create_order_with_reserves_inventory(self, client):
        self._setup_inventory(client, stock=50)
        payload = {
            **ORDER_PAYLOAD,
            "sku": "MOUSE-001",
            "quantity": 5,
            "reserve_inventory": True,
        }
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["inventory_reserved"] is True
        assert body["sku"] == "MOUSE-001"
        # Check inventory was updated
        inv = client.get("/api/v1/inventory").json()["items"][0]
        assert inv["reserved_quantity"] == 5
        assert inv["available_quantity"] == 45

    def test_create_order_without_reserve(self, client):
        self._setup_inventory(client, stock=50)
        payload = {
            **ORDER_PAYLOAD,
            "sku": "MOUSE-001",
            "quantity": 5,
            "reserve_inventory": False,
        }
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 201
        assert resp.json()["inventory_reserved"] is False
        # Inventory unchanged
        inv = client.get("/api/v1/inventory").json()["items"][0]
        assert inv["reserved_quantity"] == 0

    def test_insufficient_inventory_fails(self, client):
        self._setup_inventory(client, stock=5)
        payload = {
            **ORDER_PAYLOAD,
            "sku": "MOUSE-001",
            "quantity": 10,
            "reserve_inventory": True,
        }
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 422
        assert "error" in resp.json()

    def test_exact_available_quantity_succeeds(self, client):
        self._setup_inventory(client, stock=10)
        payload = {
            **ORDER_PAYLOAD,
            "sku": "MOUSE-001",
            "quantity": 10,
            "reserve_inventory": True,
        }
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 201
        assert resp.json()["inventory_reserved"] is True
        inv = client.get("/api/v1/inventory").json()["items"][0]
        assert inv["available_quantity"] == 0
        assert inv["status"] == "out_of_stock"

    def test_unknown_sku_fails(self, client):
        payload = {
            **ORDER_PAYLOAD,
            "sku": "NONEXISTENT",
            "quantity": 1,
            "reserve_inventory": True,
        }
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 404

    def test_reserve_existing_order(self, client):
        self._setup_inventory(client, stock=50)
        created = _create_order(client, sku="MOUSE-001", quantity=5)
        assert created["inventory_reserved"] is False
        resp = client.post(f"/api/v1/orders/{created['id']}/reserve")
        assert resp.status_code == 200
        assert resp.json()["inventory_reserved"] is True
        inv = client.get("/api/v1/inventory").json()["items"][0]
        assert inv["reserved_quantity"] == 5

    def test_reserve_already_reserved_fails(self, client):
        self._setup_inventory(client, stock=50)
        created = _create_order(client, sku="MOUSE-001", quantity=5, reserve_inventory=True)
        assert created["inventory_reserved"] is True
        resp = client.post(f"/api/v1/orders/{created['id']}/reserve")
        assert resp.status_code == 422
        assert "already reserved" in resp.json()["error"].lower()

    def test_reserve_order_without_sku_fails(self, client):
        self._setup_inventory(client, stock=50)
        created = _create_order(client)
        resp = client.post(f"/api/v1/orders/{created['id']}/reserve")
        assert resp.status_code == 422
        assert "sku" in resp.json()["error"].lower()

    def test_cancel_releases_inventory(self, client):
        self._setup_inventory(client, stock=50)
        created = _create_order(client, sku="MOUSE-001", quantity=10, reserve_inventory=True)
        inv_before = client.get("/api/v1/inventory").json()["items"][0]
        assert inv_before["reserved_quantity"] == 10
        # Cancel the order
        resp = client.patch(
            f"/api/v1/orders/{created['id']}",
            json={"status": "cancelled"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        # Check inventory released
        inv_after = client.get("/api/v1/inventory").json()["items"][0]
        assert inv_after["reserved_quantity"] == 0
        assert inv_after["available_quantity"] == 50

    def test_multiple_orders_reserve_cumulatively(self, client):
        self._setup_inventory(client, stock=50)
        _create_order(client, sku="MOUSE-001", quantity=10, reserve_inventory=True)
        _create_order(client, sku="MOUSE-001", quantity=15, reserve_inventory=True)
        inv = client.get("/api/v1/inventory").json()["items"][0]
        assert inv["reserved_quantity"] == 25
        assert inv["available_quantity"] == 25

    def test_reservation_updates_inventory_status(self, client):
        self._setup_inventory(client, stock=10)
        _create_order(client, sku="MOUSE-001", quantity=8, reserve_inventory=True)
        inv = client.get("/api/v1/inventory").json()["items"][0]
        assert inv["available_quantity"] == 2
        assert inv["status"] == "low_stock"


# ===========================================================================
# Authentication — every order endpoint requires a real JWT + organization
# ===========================================================================

class TestAuthentication:
    """No default/fallback organization: every order endpoint must reject
    unauthenticated requests, and must never trust a client-supplied
    organization_id as an authorization source."""

    def test_create_without_token_returns_401(self, client):
        client.headers.pop("Authorization", None)
        resp = client.post("/api/v1/orders", json=ORDER_PAYLOAD)
        assert resp.status_code == 401

    def test_list_without_token_returns_401(self, client):
        client.headers.pop("Authorization", None)
        resp = client.get("/api/v1/orders")
        assert resp.status_code == 401

    def test_get_without_token_returns_401(self, client):
        created = _create_order(client)
        client.headers.pop("Authorization", None)
        resp = client.get(f"/api/v1/orders/{created['id']}")
        assert resp.status_code == 401

    def test_update_without_token_returns_401(self, client):
        created = _create_order(client)
        client.headers.pop("Authorization", None)
        resp = client.patch(f"/api/v1/orders/{created['id']}", json={"status": "processing"})
        assert resp.status_code == 401

    def test_reserve_without_token_returns_401(self, client):
        created = _create_order(client)
        client.headers.pop("Authorization", None)
        resp = client.post(f"/api/v1/orders/{created['id']}/reserve")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        client.headers["Authorization"] = "Bearer not-a-real-token"
        resp = client.post("/api/v1/orders", json=ORDER_PAYLOAD)
        assert resp.status_code == 401

    def test_client_supplied_organization_id_is_not_trusted(self, client):
        """A client-supplied organization_id in the request body must never
        determine order ownership -- the server always derives it from the
        authenticated user's real organization membership."""
        other_org_id = str(uuid.uuid4())
        payload = {**ORDER_PAYLOAD, "organization_id": other_org_id}
        resp = client.post("/api/v1/orders", json=payload)
        assert resp.status_code == 201
        # The order was created under the caller's real (authenticated)
        # organization, not the fabricated one from the request body: it
        # shows up in this same authenticated caller's own list.
        listed_ids = {o["id"] for o in client.get("/api/v1/orders").json()["items"]}
        assert resp.json()["id"] in listed_ids


# ===========================================================================
# Organization isolation
# ===========================================================================

class TestOrganizationIsolation:
    """Two different real organizations must never see or modify each
    other's orders. A cross-organization lookup behaves identically to a
    missing order (404) -- existence is never leaked."""

    def test_org_a_cannot_read_org_b_order(self, client):
        org_a_headers = dict(client.headers)
        order_a = _create_order(client, customer_name="Org A Customer")

        org_b_headers = auth_headers(client)
        order_b = _create_order(client, customer_name="Org B Customer", headers=org_b_headers)

        resp = client.get(f"/api/v1/orders/{order_b['id']}", headers=org_a_headers)
        assert resp.status_code == 404

        resp = client.get(f"/api/v1/orders/{order_a['id']}", headers=org_b_headers)
        assert resp.status_code == 404

    def test_list_is_scoped_to_caller_organization(self, client):
        org_a_headers = dict(client.headers)
        order_a = _create_order(client, customer_name="Org A Customer")

        org_b_headers = auth_headers(client)
        order_b = _create_order(client, customer_name="Org B Customer", headers=org_b_headers)

        ids_a = {o["id"] for o in client.get("/api/v1/orders", headers=org_a_headers).json()["items"]}
        assert ids_a == {order_a["id"]}

        ids_b = {o["id"] for o in client.get("/api/v1/orders", headers=org_b_headers).json()["items"]}
        assert ids_b == {order_b["id"]}

    def test_org_a_cannot_update_org_b_order(self, client):
        org_a_headers = dict(client.headers)

        org_b_headers = auth_headers(client)
        order_b = _create_order(client, customer_name="Org B Customer", headers=org_b_headers)

        resp = client.patch(
            f"/api/v1/orders/{order_b['id']}",
            json={"status": "processing"},
            headers=org_a_headers,
        )
        assert resp.status_code == 404

        # Order B is genuinely untouched.
        still_pending = client.get(f"/api/v1/orders/{order_b['id']}", headers=org_b_headers).json()
        assert still_pending["status"] == "pending"

    def test_org_a_cannot_reserve_inventory_on_org_b_order(self, client):
        org_a_headers = dict(client.headers)

        org_b_headers = auth_headers(client)
        client.post(
            "/api/v1/inventory",
            json={"sku": "ISO-SKU", "product_name": "Widget", "current_stock": 10},
            headers=org_b_headers,
        )
        order_b = _create_order(client, sku="ISO-SKU", quantity=1, headers=org_b_headers)

        resp = client.post(f"/api/v1/orders/{order_b['id']}/reserve", headers=org_a_headers)
        assert resp.status_code == 404


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
