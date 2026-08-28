"""Tests for provider abstractions and mock implementations.

Covers order provider, supplier provider, tracking provider,
provider safety, and regression.
"""

import pytest

from app.services.providers.base import (
    ProviderCapabilities,
    ProviderEnvironment,
    ProviderOperationNotSupportedError,
    ProviderSubmissionBlockedError,
    ensure_mock_mode,
)
from app.services.providers.mock.order_provider import MockOrderProvider
from app.services.providers.mock.supplier_provider import MockSupplierProvider
from app.services.providers.mock.tracking_provider import MockTrackingProvider
from app.services.providers.registry import ProviderRegistry, create_default_registry

from tests.conftest import auth_headers


# ===========================================================================
# Order Provider
# ===========================================================================

class TestMockOrderProvider:
    """Mock order provider behavior."""

    def test_provider_name(self):
        provider = MockOrderProvider()
        assert provider.provider_name == "mock_order_provider"

    def test_environment_is_mock(self):
        provider = MockOrderProvider()
        assert provider.environment == ProviderEnvironment.MOCK
        assert provider.is_mock is True

    def test_capabilities(self):
        provider = MockOrderProvider()
        caps = provider.capabilities
        assert caps.supports_order_read is True
        assert caps.supports_order_list is True
        assert caps.supports_supplier_submit is False

    def test_get_existing_order(self):
        provider = MockOrderProvider()
        order = provider.get_order("MOCK-ORDER-001")
        assert order is not None
        assert order["order_id"] == "MOCK-ORDER-001"
        assert order["sku"] == "SKU-TEST-001"

    def test_get_unknown_order(self):
        provider = MockOrderProvider()
        order = provider.get_order("NONEXISTENT")
        assert order is None

    def test_list_orders(self):
        provider = MockOrderProvider()
        orders = provider.list_orders()
        assert len(orders) == 3

    def test_list_orders_with_limit(self):
        provider = MockOrderProvider()
        orders = provider.list_orders(limit=2)
        assert len(orders) == 2

    def test_list_orders_with_offset(self):
        provider = MockOrderProvider()
        orders = provider.list_orders(offset=2)
        assert len(orders) == 1

    def test_get_order_count(self):
        provider = MockOrderProvider()
        assert provider.get_order_count() == 3

    def test_all_orders_have_required_fields(self):
        provider = MockOrderProvider()
        for order in provider.list_orders():
            assert "order_id" in order
            assert "sku" in order
            assert "quantity" in order
            assert "status" in order


# ===========================================================================
# Supplier Provider
# ===========================================================================

class TestMockSupplierProvider:
    """Mock supplier provider behavior."""

    def test_provider_name(self):
        provider = MockSupplierProvider()
        assert provider.provider_name == "mock_supplier_provider"

    def test_environment_is_mock(self):
        provider = MockSupplierProvider()
        assert provider.environment == ProviderEnvironment.MOCK
        assert provider.is_mock is True

    def test_capabilities(self):
        provider = MockSupplierProvider()
        caps = provider.capabilities
        assert caps.supports_supplier_prepare is True
        assert caps.supports_supplier_verify is True
        assert caps.supports_supplier_submit is True

    def test_prepare_order(self):
        provider = MockSupplierProvider()
        result = provider.prepare_order({
            "sku": "SKU-TEST-001",
            "product_name": "Wireless Mouse",
            "quantity": 5,
            "shipping_method": "express",
        })
        assert result["prepared"] is True
        assert result["supplier"] == "MOCK SUPPLIER"
        assert result["sku"] == "SKU-TEST-001"

    def test_verify_order_valid(self):
        provider = MockSupplierProvider()
        result = provider.verify_order({
            "sku": "SKU-TEST-001",
            "quantity": 5,
        })
        assert result["verified"] is True
        assert result["issues"] == []

    def test_verify_order_missing_sku(self):
        provider = MockSupplierProvider()
        result = provider.verify_order({
            "sku": "UNKNOWN",
            "quantity": 5,
        })
        assert result["verified"] is False
        assert "Missing SKU" in result["issues"]

    def test_verify_order_invalid_quantity(self):
        provider = MockSupplierProvider()
        result = provider.verify_order({
            "sku": "SKU-TEST-001",
            "quantity": 0,
        })
        assert result["verified"] is False
        assert "Invalid quantity" in result["issues"]

    def test_submit_requires_approval(self):
        provider = MockSupplierProvider()
        with pytest.raises(ProviderSubmissionBlockedError):
            provider.submit_order({"sku": "SKU-TEST-001"}, approved=False)

    def test_submit_succeeds_after_approval(self):
        provider = MockSupplierProvider()
        result = provider.submit_order({"sku": "SKU-TEST-001"}, approved=True)
        assert result["submitted"] is True
        assert result["confirmation_id"].startswith("SUP-MOCK-")
        assert result["supplier"] == "MOCK SUPPLIER"

    def test_duplicate_submission_tracking(self):
        provider = MockSupplierProvider()
        result = provider.submit_order({"sku": "SKU-TEST-001"}, approved=True)
        confirm_id = result["confirmation_id"]
        # Check that confirmation is tracked
        assert provider.is_duplicate_submission(confirm_id) is True
        assert provider.is_duplicate_submission("NONEXISTENT") is False

    def test_clear_resets_state(self):
        provider = MockSupplierProvider()
        provider.submit_order({"sku": "SKU-TEST-001"}, approved=True)
        provider.clear()
        # Should be able to submit again after clear
        result = provider.submit_order({"sku": "SKU-TEST-001"}, approved=True)
        assert result["submitted"] is True


# ===========================================================================
# Tracking Provider
# ===========================================================================

class TestMockTrackingProvider:
    """Mock tracking provider behavior."""

    def test_provider_name(self):
        provider = MockTrackingProvider()
        assert provider.provider_name == "mock_tracking_provider"

    def test_environment_is_mock(self):
        provider = MockTrackingProvider()
        assert provider.environment == ProviderEnvironment.MOCK
        assert provider.is_mock is True

    def test_capabilities(self):
        provider = MockTrackingProvider()
        caps = provider.capabilities
        assert caps.supports_tracking_read is True
        assert caps.supports_order_read is False

    def test_get_existing_tracking(self):
        provider = MockTrackingProvider()
        tracking = provider.get_tracking("MOCK-TRACK-000001")
        assert tracking is not None
        assert tracking["tracking_id"] == "MOCK-TRACK-000001"
        assert tracking["carrier"] == "MOCK-CARRIER"
        assert tracking["status"] == "delivered"

    def test_get_unknown_tracking(self):
        provider = MockTrackingProvider()
        tracking = provider.get_tracking("NONEXISTENT")
        assert tracking is None

    def test_get_status(self):
        provider = MockTrackingProvider()
        status = provider.get_status("MOCK-TRACK-000002")
        assert status == "in_transit"

    def test_get_status_unknown(self):
        provider = MockTrackingProvider()
        status = provider.get_status("NONEXISTENT")
        assert status is None

    def test_list_tracking(self):
        provider = MockTrackingProvider()
        records = provider.list_tracking()
        assert len(records) == 3

    def test_tracking_has_events(self):
        provider = MockTrackingProvider()
        tracking = provider.get_tracking("MOCK-TRACK-000001")
        assert len(tracking["events"]) > 0
        for event in tracking["events"]:
            assert "timestamp" in event
            assert "status" in event
            assert "location" in event

    def test_generate_tracking_id(self):
        provider = MockTrackingProvider()
        tid = provider.generate_tracking_id()
        assert tid.startswith("MOCK-TRACK-")


# ===========================================================================
# Provider Registry
# ===========================================================================

class TestProviderRegistry:
    """Provider registry behavior."""

    def test_create_default_registry(self):
        registry = create_default_registry()
        assert registry.get("mock_order_provider") is not None
        assert registry.get("mock_supplier_provider") is not None
        assert registry.get("mock_tracking_provider") is not None

    def test_list_all_providers(self):
        registry = create_default_registry()
        providers = registry.list_all()
        assert len(providers) == 3

    def test_all_providers_are_mock(self):
        registry = create_default_registry()
        for p in registry.list_all():
            assert p["is_mock"] is True
            assert p["environment"] in ("mock", "sandbox")

    def test_get_order_provider(self):
        registry = create_default_registry()
        provider = registry.get_order_provider()
        assert isinstance(provider, MockOrderProvider)

    def test_get_supplier_provider(self):
        registry = create_default_registry()
        provider = registry.get_supplier_provider()
        assert isinstance(provider, MockSupplierProvider)

    def test_get_tracking_provider(self):
        registry = create_default_registry()
        provider = registry.get_tracking_provider()
        assert isinstance(provider, MockTrackingProvider)


# ===========================================================================
# Provider Safety
# ===========================================================================

class TestProviderSafety:
    """Provider safety mechanisms."""

    def test_mock_mode_is_active(self):
        """Ensure mock mode is active."""
        from app.services.providers.base import MOCK_ONLY
        assert MOCK_ONLY is True

    def test_ensure_mock_mode_does_not_raise(self):
        """ensure_mock_mode should not raise in mock mode."""
        ensure_mock_mode()  # Should not raise

    def test_no_external_requests_in_mock_providers(self):
        """Verify mock providers don't make external requests."""
        # Mock providers use hardcoded data — no HTTP calls
        order_provider = MockOrderProvider()
        order = order_provider.get_order("MOCK-ORDER-001")
        assert order is not None  # Data is local

    def test_supplier_provider_uses_local_sandbox(self):
        """Supplier provider should use local sandbox only."""
        provider = MockSupplierProvider()
        result = provider.prepare_order({"sku": "TEST", "quantity": 1})
        assert result["supplier"] == "MOCK SUPPLIER"

    def test_tracking_provider_uses_local_data(self):
        """Tracking provider should use local data only."""
        provider = MockTrackingProvider()
        tracking = provider.get_tracking("MOCK-TRACK-000001")
        assert tracking["carrier"] == "MOCK-CARRIER"


# ===========================================================================
# Regression
# ===========================================================================

class TestRegression:
    """Ensure existing functionality still works."""

    def test_health_endpoints(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            assert c.get("/health").status_code == 200
            assert c.get("/api/v1/health").status_code == 200
            assert c.get("/api/v1/status").status_code == 200

    def test_provider_endpoints(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            resp = c.get("/api/v1/providers")
            assert resp.status_code == 200
            body = resp.json()
            assert body["mock_only"] is True
            assert len(body["providers"]) == 3

    def test_provider_orders_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            resp = c.get("/api/v1/providers/orders")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 3

    def test_provider_tracking_endpoint(self):
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            resp = c.get("/api/v1/providers/tracking")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 3

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
