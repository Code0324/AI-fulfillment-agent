"""Tests for the generic Inventory API endpoints.

Covers POST, GET list (paginated + filtered), GET by ID, PATCH — plus 404,
validation errors, quantity validation, low-stock detection,
out-of-stock detection, and regression checks.
"""

import uuid

import pytest

from app.services.inventory_service import inventory_service


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_inventory_service():
    """Clear in-memory store before every test so tests are independent."""
    inventory_service.clear()
    yield
    inventory_service.clear()


INVENTORY_PAYLOAD = {
    "sku": "WIRELESS-MOUSE-001",
    "product_name": "Wireless Mouse",
    "current_stock": 50,
    "reserved_quantity": 0,
    "low_stock_threshold": 10,
}


def _create_inventory(client, **overrides):
    """Helper: create an inventory item and return the response JSON."""
    payload = {**INVENTORY_PAYLOAD, **overrides}
    return client.post("/api/v1/inventory", json=payload).json()


# ===========================================================================
# POST /api/v1/inventory
# ===========================================================================

class TestCreateInventoryItem:
    """POST /api/v1/inventory"""

    def test_create_inventory_item(self, client):
        resp = client.post("/api/v1/inventory", json=INVENTORY_PAYLOAD)
        assert resp.status_code == 201
        body = resp.json()
        assert body["sku"] == "WIRELESS-MOUSE-001"
        assert body["product_name"] == "Wireless Mouse"
        assert body["current_stock"] == 50
        assert body["reserved_quantity"] == 0
        assert body["available_quantity"] == 50
        assert body["low_stock_threshold"] == 10
        assert body["status"] == "in_stock"
        assert "id" in body
        assert "created_at" in body
        assert "updated_at" in body

    def test_create_with_reserved_quantity(self, client):
        payload = {**INVENTORY_PAYLOAD, "reserved_quantity": 5}
        resp = client.post("/api/v1/inventory", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["reserved_quantity"] == 5
        assert body["available_quantity"] == 45

    def test_create_low_stock_item(self, client):
        payload = {**INVENTORY_PAYLOAD, "current_stock": 5, "low_stock_threshold": 10}
        resp = client.post("/api/v1/inventory", json=payload)
        assert resp.status_code == 201
        assert resp.json()["status"] == "low_stock"

    def test_create_out_of_stock_item(self, client):
        payload = {**INVENTORY_PAYLOAD, "current_stock": 0}
        resp = client.post("/api/v1/inventory", json=payload)
        assert resp.status_code == 201
        assert resp.json()["status"] == "out_of_stock"

    def test_create_reserved_equals_stock(self, client):
        """reserved == current_stock means available = 0 → out_of_stock"""
        payload = {**INVENTORY_PAYLOAD, "current_stock": 10, "reserved_quantity": 10}
        resp = client.post("/api/v1/inventory", json=payload)
        assert resp.status_code == 201
        assert resp.json()["status"] == "out_of_stock"
        assert resp.json()["available_quantity"] == 0

    def test_create_reserved_exceeds_stock_returns_422(self, client):
        payload = {**INVENTORY_PAYLOAD, "current_stock": 5, "reserved_quantity": 10}
        resp = client.post("/api/v1/inventory", json=payload)
        assert resp.status_code == 422

    def test_create_missing_sku_returns_422(self, client):
        payload = {**INVENTORY_PAYLOAD, "sku": ""}
        resp = client.post("/api/v1/inventory", json=payload)
        assert resp.status_code == 422

    def test_create_missing_product_name_returns_422(self, client):
        payload = {**INVENTORY_PAYLOAD, "product_name": ""}
        resp = client.post("/api/v1/inventory", json=payload)
        assert resp.status_code == 422

    def test_create_negative_stock_returns_422(self, client):
        payload = {**INVENTORY_PAYLOAD, "current_stock": -1}
        resp = client.post("/api/v1/inventory", json=payload)
        assert resp.status_code == 422

    def test_create_negative_reserved_returns_422(self, client):
        payload = {**INVENTORY_PAYLOAD, "reserved_quantity": -1}
        resp = client.post("/api/v1/inventory", json=payload)
        assert resp.status_code == 422

    def test_create_negative_threshold_returns_422(self, client):
        payload = {**INVENTORY_PAYLOAD, "low_stock_threshold": -1}
        resp = client.post("/api/v1/inventory", json=payload)
        assert resp.status_code == 422

    def test_create_returns_unique_id(self, client):
        r1 = client.post("/api/v1/inventory", json=INVENTORY_PAYLOAD).json()
        r2 = client.post("/api/v1/inventory", json=INVENTORY_PAYLOAD).json()
        assert r1["id"] != r2["id"]


# ===========================================================================
# GET /api/v1/inventory  (paginated)
# ===========================================================================

class TestListInventoryItems:
    """GET /api/v1/inventory — paginated response."""

    def test_empty_list_returns_paginated_response(self, client):
        resp = client.get("/api/v1/inventory")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["page"] == 1
        assert body["page_size"] == 10
        assert body["total_items"] == 0
        assert body["total_pages"] == 0

    def test_returns_created_items_in_items(self, client):
        _create_inventory(client, sku="SKU-001")
        _create_inventory(client, sku="SKU-002")
        resp = client.get("/api/v1/inventory")
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total_items"] == 2

    def test_list_preserves_insertion_order(self, client):
        r1 = _create_inventory(client, sku="FIRST")
        r2 = _create_inventory(client, sku="SECOND")
        items = client.get("/api/v1/inventory").json()["items"]
        assert items[0]["id"] == r1["id"]
        assert items[1]["id"] == r2["id"]

    def test_response_is_paginated_type(self, client):
        resp = client.get("/api/v1/inventory")
        body = resp.json()
        assert isinstance(body["items"], list)
        assert isinstance(body["page"], int)
        assert isinstance(body["page_size"], int)
        assert isinstance(body["total_items"], int)
        assert isinstance(body["total_pages"], int)

    def test_page_2_returns_second_slice(self, client):
        for i in range(15):
            _create_inventory(client, sku=f"SKU-{i:03d}")
        resp = client.get("/api/v1/inventory?page=2&page_size=10").json()
        assert len(resp["items"]) == 5
        assert resp["page"] == 2

    def test_page_beyond_total_returns_empty_items(self, client):
        _create_inventory(client)
        resp = client.get("/api/v1/inventory?page=99&page_size=10").json()
        assert resp["items"] == []
        assert resp["total_items"] == 1

    def test_total_pages_calculation(self, client):
        for i in range(25):
            _create_inventory(client, sku=f"SKU-{i:03d}")
        resp = client.get("/api/v1/inventory?page_size=10").json()
        assert resp["total_pages"] == 3

    def test_page_0_returns_422(self, client):
        resp = client.get("/api/v1/inventory?page=0")
        assert resp.status_code == 422

    def test_page_size_0_returns_422(self, client):
        resp = client.get("/api/v1/inventory?page_size=0")
        assert resp.status_code == 422

    def test_large_page_size_caps_at_100(self, client):
        resp = client.get("/api/v1/inventory?page_size=101")
        assert resp.status_code == 422


# ===========================================================================
# GET /api/v1/inventory/{item_id}
# ===========================================================================

class TestGetInventoryItem:
    """GET /api/v1/inventory/{item_id}"""

    def test_get_existing_item(self, client):
        created = _create_inventory(client)
        resp = client.get(f"/api/v1/inventory/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_missing_item_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/inventory/{fake_id}")
        assert resp.status_code == 404

    def test_get_404_body_has_error_key(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/inventory/{fake_id}")
        assert "error" in resp.json()

    def test_get_returns_correct_fields(self, client):
        created = _create_inventory(client)
        resp = client.get(f"/api/v1/inventory/{created['id']}").json()
        assert set(resp.keys()) == {
            "id", "sku", "product_name", "current_stock", "reserved_quantity",
            "available_quantity", "low_stock_threshold", "status",
            "created_at", "updated_at",
        }
        assert resp["sku"] == "WIRELESS-MOUSE-001"
        assert resp["current_stock"] == 50


# ===========================================================================
# PATCH /api/v1/inventory/{item_id}
# ===========================================================================

class TestUpdateInventoryItem:
    """PATCH /api/v1/inventory/{item_id}"""

    def test_update_current_stock(self, client):
        created = _create_inventory(client)
        resp = client.patch(
            f"/api/v1/inventory/{created['id']}",
            json={"current_stock": 100},
        )
        assert resp.status_code == 200
        assert resp.json()["current_stock"] == 100
        assert resp.json()["available_quantity"] == 100

    def test_update_reserved_quantity(self, client):
        created = _create_inventory(client)
        resp = client.patch(
            f"/api/v1/inventory/{created['id']}",
            json={"reserved_quantity": 5},
        )
        assert resp.status_code == 200
        assert resp.json()["reserved_quantity"] == 5
        assert resp.json()["available_quantity"] == 45

    def test_update_low_stock_threshold(self, client):
        created = _create_inventory(client)
        resp = client.patch(
            f"/api/v1/inventory/{created['id']}",
            json={"low_stock_threshold": 20},
        )
        assert resp.status_code == 200
        assert resp.json()["low_stock_threshold"] == 20

    def test_update_recomputes_status_to_low_stock(self, client):
        created = _create_inventory(client)
        resp = client.patch(
            f"/api/v1/inventory/{created['id']}",
            json={"current_stock": 5},
        )
        assert resp.json()["status"] == "low_stock"

    def test_update_recomputes_status_to_out_of_stock(self, client):
        created = _create_inventory(client)
        resp = client.patch(
            f"/api/v1/inventory/{created['id']}",
            json={"current_stock": 0},
        )
        assert resp.json()["status"] == "out_of_stock"

    def test_update_reserved_exceeds_stock_returns_422(self, client):
        created = _create_inventory(client, current_stock=10)
        resp = client.patch(
            f"/api/v1/inventory/{created['id']}",
            json={"current_stock": 5, "reserved_quantity": 10},
        )
        assert resp.status_code == 422

    def test_update_missing_item_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.patch(f"/api/v1/inventory/{fake_id}", json={"current_stock": 10})
        assert resp.status_code == 404

    def test_update_empty_body_returns_422(self, client):
        created = _create_inventory(client)
        resp = client.patch(f"/api/v1/inventory/{created['id']}", json={})
        assert resp.status_code == 422

    def test_update_updates_timestamp(self, client):
        created = _create_inventory(client)
        resp = client.patch(
            f"/api/v1/inventory/{created['id']}",
            json={"current_stock": 100},
        )
        assert resp.json()["updated_at"] >= created["updated_at"]

    def test_update_negative_stock_returns_422(self, client):
        created = _create_inventory(client)
        resp = client.patch(
            f"/api/v1/inventory/{created['id']}",
            json={"current_stock": -1},
        )
        assert resp.status_code == 422

    def test_update_negative_reserved_returns_422(self, client):
        created = _create_inventory(client)
        resp = client.patch(
            f"/api/v1/inventory/{created['id']}",
            json={"reserved_quantity": -1},
        )
        assert resp.status_code == 422


# ===========================================================================
# Status filtering
# ===========================================================================

class TestFilterByStatus:
    """GET /api/v1/inventory?status=... filtering."""

    def test_filter_in_stock(self, client):
        _create_inventory(client, sku="A", current_stock=50)
        _create_inventory(client, sku="B", current_stock=0)
        resp = client.get("/api/v1/inventory?status=in_stock").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["sku"] == "A"

    def test_filter_low_stock(self, client):
        _create_inventory(client, sku="A", current_stock=5)
        _create_inventory(client, sku="B", current_stock=50)
        resp = client.get("/api/v1/inventory?status=low_stock").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["sku"] == "A"

    def test_filter_out_of_stock(self, client):
        _create_inventory(client, sku="A", current_stock=0)
        _create_inventory(client, sku="B", current_stock=50)
        resp = client.get("/api/v1/inventory?status=out_of_stock").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["sku"] == "A"

    def test_filter_no_match(self, client):
        _create_inventory(client, current_stock=50)
        resp = client.get("/api/v1/inventory?status=out_of_stock").json()
        assert resp["items"] == []
        assert resp["total_items"] == 0

    def test_filter_invalid_status_returns_422(self, client):
        resp = client.get("/api/v1/inventory?status=bogus")
        assert resp.status_code == 422

    def test_no_filter_returns_all(self, client):
        _create_inventory(client, current_stock=50)
        _create_inventory(client, current_stock=5)
        _create_inventory(client, current_stock=0)
        resp = client.get("/api/v1/inventory").json()
        assert resp["total_items"] == 3


# ===========================================================================
# Search filtering
# ===========================================================================

class TestSearchInventory:
    """GET /api/v1/inventory?search=... text search."""

    def test_search_by_sku(self, client):
        _create_inventory(client, sku="WIRELESS-MOUSE-001", product_name="Mouse Device")
        _create_inventory(client, sku="USB-KEYBOARD-001", product_name="Keyboard Device")
        resp = client.get("/api/v1/inventory?search=mouse").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["sku"] == "WIRELESS-MOUSE-001"

    def test_search_by_product_name(self, client):
        _create_inventory(client, sku="MOUSE-01", product_name="Wireless Mouse")
        _create_inventory(client, sku="KB-01", product_name="USB Keyboard")
        resp = client.get("/api/v1/inventory?search=keyboard").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["product_name"] == "USB Keyboard"

    def test_search_case_insensitive(self, client):
        _create_inventory(client, sku="WIRELESS-MOUSE-001")
        resp = client.get("/api/v1/inventory?search=Wireless").json()
        assert resp["total_items"] == 1

    def test_search_partial_match(self, client):
        _create_inventory(client, sku="WIRELESS-MOUSE-001")
        _create_inventory(client, sku="WIRELESS-KEYBOARD-001")
        resp = client.get("/api/v1/inventory?search=wireless").json()
        assert resp["total_items"] == 2

    def test_search_no_results(self, client):
        _create_inventory(client)
        resp = client.get("/api/v1/inventory?search=nonexistent").json()
        assert resp["total_items"] == 0
        assert resp["items"] == []

    def test_search_empty_string_returns_all(self, client):
        _create_inventory(client, sku="A")
        _create_inventory(client, sku="B")
        resp = client.get("/api/v1/inventory?search=").json()
        assert resp["total_items"] == 2

    def test_search_combined_with_status_filter(self, client):
        _create_inventory(client, sku="MOUSE-01", product_name="Mouse", current_stock=50)
        _create_inventory(client, sku="MOUSE-02", product_name="Mouse", current_stock=0)
        _create_inventory(client, sku="KB-01", product_name="Keyboard", current_stock=50)
        resp = client.get("/api/v1/inventory?search=mouse&status=in_stock").json()
        assert resp["total_items"] == 1
        assert resp["items"][0]["sku"] == "MOUSE-01"


# ===========================================================================
# Low-stock and out-of-stock detection
# ===========================================================================

class TestStockDetection:
    """Verify low-stock and out-of-stock status detection."""

    def test_in_stock_when_above_threshold(self, client):
        resp = _create_inventory(client, current_stock=50, low_stock_threshold=10)
        assert resp["status"] == "in_stock"
        assert resp["available_quantity"] == 50

    def test_low_stock_when_at_threshold(self, client):
        resp = _create_inventory(client, current_stock=10, low_stock_threshold=10)
        assert resp["status"] == "low_stock"
        assert resp["available_quantity"] == 10

    def test_low_stock_when_below_threshold(self, client):
        resp = _create_inventory(client, current_stock=4, low_stock_threshold=10)
        assert resp["status"] == "low_stock"

    def test_out_of_stock_when_zero_stock(self, client):
        resp = _create_inventory(client, current_stock=0, low_stock_threshold=10)
        assert resp["status"] == "out_of_stock"

    def test_out_of_stock_when_reserved_equals_stock(self, client):
        resp = _create_inventory(client, current_stock=10, reserved_quantity=10)
        assert resp["status"] == "out_of_stock"
        assert resp["available_quantity"] == 0

    def test_low_stock_with_reservations(self, client):
        resp = _create_inventory(client, current_stock=15, reserved_quantity=8, low_stock_threshold=10)
        assert resp["status"] == "low_stock"
        assert resp["available_quantity"] == 7

    def test_in_stock_after_restock(self, client):
        created = _create_inventory(client, current_stock=5, low_stock_threshold=10)
        assert created["status"] == "low_stock"
        resp = client.patch(
            f"/api/v1/inventory/{created['id']}",
            json={"current_stock": 50},
        )
        assert resp.json()["status"] == "in_stock"


# ===========================================================================
# Regression — existing routes still work
# ===========================================================================

class TestRegressionExistingRoutes:
    """Ensure health / status routes are unaffected by inventory routes."""

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


# ===========================================================================
# Concurrency — reservation must never oversell under concurrent requests
# ===========================================================================

class TestConcurrentReservation:
    """Regression: reserve() must serialize compound read-modify-write.

    Without locking, concurrent threads can each read the same
    available_quantity, all pass the check, and collectively reserve more
    than current_stock — a real oversell bug under concurrent order
    submission (e.g. duplicate clicks, retried requests, race between
    orders for the same tight-stock SKU).
    """

    def test_concurrent_reserve_never_exceeds_stock(self, client):
        import threading

        item = _create_inventory(
            client, sku="RACE-SKU", current_stock=10, reserved_quantity=0
        )

        successes = []
        lock = threading.Lock()

        threads = [
            threading.Thread(target=_safe_reserve, args=(successes, lock))
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final = inventory_service.find_by_sku("RACE-SKU")
        assert final.reserved_quantity <= final.current_stock, (
            f"Oversold: reserved={final.reserved_quantity} "
            f"stock={final.current_stock}"
        )
        # 10 concurrent requests for 3 units each against 10 in stock:
        # exactly 3 can succeed (9 <= 10), the rest must be rejected.
        assert len(successes) == 3


def _safe_reserve(successes, lock):
    """Helper: attempt a reservation, recording only successes."""
    try:
        inventory_service.reserve("RACE-SKU", 3)
        with lock:
            successes.append(1)
    except Exception:
        pass
