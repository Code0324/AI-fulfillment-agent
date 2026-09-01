"""Tests for TikTok order ingestion, SKU mapping confirmation, and the
dashboard summary endpoint — the new pieces wired up for the TikTok ->
Sheet -> Amazon fulfillment business workflow.

NOTE: like the rest of this test suite, these hit a real PostgreSQL
database via the app's normal DB session — there is no mock/sqlite
fallback (see tests/conftest.py). They were written against the app's
actual code paths but could not be executed in the sandboxed development
environment used to write them (no reachable PostgreSQL instance).
"""

from datetime import datetime, timezone

import pytest

from app.schemas.tiktok import TikTokOrder
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.inventory_service import inventory_service
from app.services.order_service import order_service
from app.services.providers.registry import provider_registry

from tests.conftest import auth_headers


@pytest.fixture(autouse=True)
def _reset_all():
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    yield
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()


class _FakeTikTokProvider:
    """Minimal stand-in for TikTokOrderProvider — returns canned orders
    without making any real HTTP calls."""

    def __init__(self, orders: list[TikTokOrder]):
        self._orders = orders

    def get_orders(self, *, limit: int = 100, offset: int = 0) -> list[TikTokOrder]:
        return self._orders[offset : offset + limit]


def _fake_order(order_id: str = "TT-10001") -> TikTokOrder:
    return TikTokOrder(
        tiktok_order_id=order_id,
        order_date=datetime.now(timezone.utc),
        sku="ABC-M",
        product_name="Premium Shirt",
        variation="Red/M",
        quantity=2,
        recipient_name="Jane Doe",
        phone_number="555-0100",
        address_line_1="123 Main St",
        delivery_instructions="Leave at door",
        city="Springfield",
        state="IL",
        zipcode="62704",
        price=31.99,
        delivery_date=None,
        order_status="AWAITING_SHIPMENT",
    )


class TestTikTokSyncEndpoint:
    def test_sync_when_not_configured_creates_nothing(self, client, monkeypatch):
        monkeypatch.setattr(provider_registry, "get_tiktok_provider", lambda: None)
        headers = auth_headers(client)
        resp = client.post("/api/v1/tiktok/sync", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is False
        assert body["created"] == 0

    def test_sync_creates_order_and_is_idempotent(self, client, monkeypatch):
        fake_order = _fake_order()
        monkeypatch.setattr(
            provider_registry, "get_tiktok_provider", lambda: _FakeTikTokProvider([fake_order])
        )
        headers = auth_headers(client)

        resp = client.post("/api/v1/tiktok/sync", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is True
        assert body["created"] == 1
        assert body["skipped_existing"] == 0

        orders_resp = client.get("/api/v1/orders?source=TIKTOK", headers=headers)
        assert orders_resp.status_code == 200
        items = orders_resp.json()["items"]
        assert len(items) == 1
        order = items[0]
        assert order["tiktok_order_id"] == "TT-10001"
        assert order["sku"] == "ABC-M"
        assert order["variation"] == "Red/M"
        assert order["source"] == "TIKTOK"
        assert order["channel_metadata"]["price"] == 31.99

        # Re-sync with the same order — idempotent via the DB unique
        # constraint on (organization_id, tiktok_order_id).
        resp2 = client.post("/api/v1/tiktok/sync", headers=headers)
        body2 = resp2.json()
        assert body2["created"] == 0
        assert body2["skipped_existing"] == 1

    def test_sync_requires_authentication(self, client, monkeypatch):
        monkeypatch.setattr(provider_registry, "get_tiktok_provider", lambda: None)
        resp = client.post("/api/v1/tiktok/sync")
        assert resp.status_code in (401, 403)


class TestSkuMappingsEndpoint:
    def test_create_mapping_returns_matched(self, client):
        headers = auth_headers(client)
        resp = client.post(
            "/api/v1/sku-mappings",
            json={
                "tiktok_sku": "ABC-M",
                "variation": "Red/M",
                "amazon_sku": "AMZ-SHIRT-RED-M",
                "asin": "B00TESTASIN",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "matched"
        assert body["amazon_sku"] == "AMZ-SHIRT-RED-M"
        assert body["source"] == "explicit"

    def test_create_mapping_requires_authentication(self, client):
        resp = client.post(
            "/api/v1/sku-mappings",
            json={"tiktok_sku": "X", "amazon_sku": "Y"},
        )
        assert resp.status_code in (401, 403)


class TestDashboardSummary:
    def test_summary_structure_with_no_orders(self, client):
        headers = auth_headers(client)
        resp = client.get("/api/v1/dashboard/summary", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"connections", "counts", "activity", "approval_queue"}
        assert body["counts"] == {
            "new": 0, "processing": 0, "awaiting_approval": 0, "completed": 0, "errors": 0,
        }
        assert body["activity"] == []
        assert body["approval_queue"] == []

    def test_summary_counts_new_order_after_sync(self, client, monkeypatch):
        monkeypatch.setattr(provider_registry, "get_tiktok_provider", lambda: None)
        monkeypatch.setattr(
            provider_registry, "get_tiktok_provider", lambda: _FakeTikTokProvider([_fake_order("TT-20001")])
        )
        headers = auth_headers(client)
        client.post("/api/v1/tiktok/sync", headers=headers)

        resp = client.get("/api/v1/dashboard/summary", headers=headers)
        body = resp.json()
        total = sum(body["counts"].values())
        assert total == 1
