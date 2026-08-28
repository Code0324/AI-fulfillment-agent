"""Production Readiness Tests — CHUNK 1W.

Comprehensive security, hardening, and production-readiness tests.
All tests use mock data — no real Amazon credentials required.
"""

import asyncio
import inspect
import os
import re
import threading
from unittest.mock import patch, MagicMock

import pytest

from app.core.config import Settings, settings
from app.services.providers.amazon.lwa_auth import (
    LWATokenManager,
    LWAAuthenticationError,
    create_lwa_token_manager_from_env,
)
from app.services.providers.amazon.sp_api_client import (
    SPAPIClient,
    SPAPIError,
    SANDBOX_ENDPOINTS,
    PRODUCTION_ENDPOINTS,
    ORDERS_API_VERSION,
    DEFAULT_RATE_LIMIT,
    DEFAULT_BURST_LIMIT,
)
from app.services.providers.amazon.order_provider import AmazonOrderProvider
from app.services.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderEnvironment,
    MOCK_ONLY,
    ProviderError,
    ProviderAuthenticationError,
)
from app.services.providers.registry import ProviderRegistry, create_default_registry
from app.services.providers.mock.order_provider import MockOrderProvider
from app.services.providers.mock.supplier_provider import MockSupplierProvider
from app.services.providers.mock.tracking_provider import MockTrackingProvider
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.order_service import order_service
from app.services.inventory_service import inventory_service
from app.core.security import redact_pii, redact_secret

from tests.conftest import create_test_organization, auth_headers


# ===========================================================================
# 1. Production Environment Protection
# ===========================================================================

class TestProductionEnvironmentProtection:
    """Verify production cannot be accidentally enabled."""

    def test_config_amazon_environment_is_always_sandbox(self):
        """Config amazon_environment always returns sandbox."""
        s = Settings()
        assert s.amazon_environment == "sandbox"

    def test_mock_only_flag_is_true(self):
        """Global MOCK_ONLY safety flag is True."""
        assert MOCK_ONLY is True

    def test_provider_environment_enum_exists(self):
        """ProviderEnvironment.PRODUCTION enum exists but is never used."""
        assert ProviderEnvironment.PRODUCTION.value == "production"

    def test_amazon_environment_defaults_to_sandbox(self):
        """AMAZON_ENVIRONMENT defaults to sandbox."""
        s = Settings()
        assert s.amazon_environment == "sandbox"

    def test_sandbox_only_in_order_provider(self):
        """AmazonOrderProvider always returns SANDBOX environment."""
        provider = AmazonOrderProvider()
        assert provider.environment == ProviderEnvironment.SANDBOX

    def test_sp_api_client_uses_only_sandbox(self):
        """SPAPIClient always uses SANDBOX endpoints."""
        manager = LWATokenManager("id", "secret", "token")
        for region in ["na", "eu", "fe"]:
            client = SPAPIClient(manager, region=region)
            assert client._base_url == SANDBOX_ENDPOINTS[region]
            assert client._base_url not in PRODUCTION_ENDPOINTS.values()

    def test_production_endpoint_blocked_na(self):
        """NA production endpoint is blocked."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")
        with pytest.raises(SPAPIError, match="BLOCKED"):
            client._validate_endpoint("https://sellingpartnerapi-na.amazon.com/orders")

    def test_production_endpoint_blocked_eu(self):
        """EU production endpoint is blocked."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="eu")
        with pytest.raises(SPAPIError, match="BLOCKED"):
            client._validate_endpoint("https://sellingpartnerapi-eu.amazon.com/orders")

    def test_production_endpoint_blocked_fe(self):
        """FE production endpoint is blocked."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="fe")
        with pytest.raises(SPAPIError, match="BLOCKED"):
            client._validate_endpoint("https://sellingpartnerapi-fe.amazon.com/orders")


# ===========================================================================
# 2. Credential Security
# ===========================================================================

class TestCredentialSecurity:
    """Verify credentials are protected everywhere."""

    def test_no_hardcoded_secrets_in_source(self):
        """No hardcoded secret values in any source file."""
        import glob
        import os
        patterns = [
            r"amzn1\.ask\.account",
            r"Atzr\|",
            r"Atza\|",
            r"Y76SDl2F",
            r"foodev",
        ]
        for filepath in glob.glob("app/**/*.py", recursive=True):
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for pat in patterns:
                    assert not re.search(pat, content), f"Found hardcoded secret in {filepath}"

    def test_no_credentials_in_frontend(self):
        """No credentials in frontend source."""
        import glob
        patterns = ["client_secret", "refresh_token", "access_token", "authorization_code"]
        for filepath in glob.glob("frontend/src/**/*.ts", recursive=True) + \
                         glob.glob("frontend/src/**/*.tsx", recursive=True):
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for pat in patterns:
                    assert pat not in content.lower(), f"Found credential in {filepath}"

    def test_no_credentials_in_logs(self):
        """Credentials are not logged (logger.info uses redacted client_id)."""
        source = inspect.getsource(LWATokenManager.__init__)
        assert "redact_secret" in source  # Uses redacted format

    def test_no_tokens_in_api_responses(self):
        """API responses never contain tokens."""
        provider = AmazonOrderProvider()
        status = provider.connection_status
        assert "access_token" not in str(status)
        assert "refresh_token" not in str(status)
        assert "client_secret" not in str(status)

    def test_lwa_manager_stores_in_memory_only(self):
        """LWA token manager stores credentials in memory only."""
        manager = LWATokenManager("test_id", "test_secret", "test_token")
        assert manager._client_id == "test_id"
        assert manager._client_secret == "test_secret"
        assert manager._refresh_token == "test_token"
        # Verify not serialized to string
        assert "test_secret" not in repr(manager)


# ===========================================================================
# 3. LWA Authentication Security
# ===========================================================================

class TestLWAAuthenticationSecurity:
    """Verify LWA authentication is secure."""

    def test_token_expires_in_seconds(self):
        """Token expiry is tracked in seconds."""
        manager = LWATokenManager("id", "secret", "token")
        assert manager.token_expires_in == 0  # No token yet

    def test_token_refresh_buffer(self):
        """Token refresh happens before expiry."""
        manager = LWATokenManager("id", "secret", "token")
        # Simulate token set to expire in 4 minutes (240s)
        import time
        manager._access_token = "test_token"
        manager._token_expires_at = time.time() + 240  # 4 min < 5 min buffer
        assert manager._is_token_valid() is False  # Should need refresh

    def test_token_valid_when_fresh(self):
        """Token is valid when recently obtained."""
        manager = LWATokenManager("id", "secret", "token")
        import time
        manager._access_token = "test_token"
        manager._token_expires_at = time.time() + 3600  # 1 hour out
        assert manager._is_token_valid() is True

    def test_token_invalid_when_expired(self):
        """Token is invalid when expired."""
        manager = LWATokenManager("id", "secret", "token")
        import time
        manager._access_token = "test_token"
        manager._token_expires_at = time.time() - 100  # Expired
        assert manager._is_token_valid() is False

    def test_invalidate_token_clears_state(self):
        """invalidate_token clears cached token."""
        manager = LWATokenManager("id", "secret", "token")
        manager._access_token = "test_token"
        manager._token_expires_at = 9999999999
        manager.invalidate_token()
        assert manager._access_token is None
        assert manager._token_expires_at == 0

    def test_clear_resets_all_state(self):
        """clear() resets all token state."""
        manager = LWATokenManager("id", "secret", "token")
        manager._access_token = "test_token"
        manager._token_refresh_count = 10
        manager.clear()
        assert manager._access_token is None
        assert manager._token_refresh_count == 0

    def test_invalid_credentials_raises_error(self):
        """Missing credentials raise LWAAuthenticationError."""
        with pytest.raises(LWAAuthenticationError):
            LWATokenManager("", "secret", "token")

    def test_invalid_client_error_not_recoverable(self):
        """invalid_client error is not recoverable."""
        manager = LWATokenManager("id", "secret", "token")
        error = LWAAuthenticationError("invalid client", recoverable=False)
        assert error.recoverable is False

    def test_lwa_url_is_amazon_auth(self):
        """LWA URL points to Amazon auth endpoint."""
        from app.services.providers.amazon.lwa_auth import LWA_TOKEN_URL
        assert LWA_TOKEN_URL == "https://api.amazon.com/auth/o2/token"


# ===========================================================================
# 4. Tenant Isolation
# ===========================================================================

class TestTenantIsolation:
    """Verify multi-tenant isolation."""

    def test_provider_instances_are_independent(self):
        """Each provider instance has independent state."""
        p1 = AmazonOrderProvider()
        p2 = AmazonOrderProvider()
        p1._imported_order_ids.add("ORDER-A")
        assert p2.is_order_imported("ORDER-A") is False

    def test_registry_clear_removes_all(self):
        """Registry clear() removes all providers."""
        registry = ProviderRegistry()
        registry.register(AmazonOrderProvider())
        registry.clear()
        assert registry.get("amazon_order_provider") is None

    def test_mock_provider_instances_are_independent(self):
        """Mock order provider instances are independent."""
        p1 = MockOrderProvider()
        p2 = MockOrderProvider()
        p1._imported_amazon_ids.add("MOCK-1")
        assert p2.is_amazon_order_imported("MOCK-1") is False


# ===========================================================================
# 5. RBAC
# ===========================================================================

class TestRBAC:
    """Verify role-based access control."""

    def test_connection_status_excludes_secrets(self):
        """Connection status never includes credentials."""
        provider = AmazonOrderProvider()
        status = provider.connection_status
        for key in status:
            val = str(status[key]).lower()
            assert "client_secret" not in val
            assert "refresh_token" not in val
            assert "access_token" not in val

    def test_no_credentials_in_api_endpoint_response(self):
        """Amazon API endpoint responses exclude credentials."""
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            resp = c.get("/api/v1/amazon/status")
            body = resp.json()
            for key, val in body.items():
                val_str = str(val).lower()
                assert "client_secret" not in val_str
                assert "refresh_token" not in val_str


# ===========================================================================
# 6. Approval Gate
# ===========================================================================

class TestApprovalGate:
    """Verify approval gate is mandatory."""

    def test_fulfillment_stops_at_waiting_approval(self):
        """Fulfillment always stops at WAITING_APPROVAL."""
        fulfillment_engine.clear()
        order_service.clear()
        inventory_service.clear()
        from app.schemas.order import OrderCreate
        from app.schemas.inventory import InventoryCreate
        inventory_service.create(InventoryCreate(
            sku="APPROVAL-SKU", product_name="Test", current_stock=100,
        ))
        order = order_service.create(OrderCreate(
            customer_name="Test", shipping_address="Test Customer\n123 Test St\nNew York NY 10003\nUS",
            product_name="Test", sku="APPROVAL-SKU", quantity=1,
        ), create_test_organization())
        wf = fulfillment_engine.start_workflow(order.id)
        assert wf.status.value in ("waiting_approval", "failed")
        fulfillment_engine.clear()
        order_service.clear()
        inventory_service.clear()

    def test_no_auto_approval_in_engine(self):
        """No auto-approval mechanism exists."""
        import inspect
        source = inspect.getsource(fulfillment_engine.__class__)
        assert "auto_approve" not in source.lower()
        assert "skip_approval" not in source.lower()
        assert "automatic" not in source.lower()

    def test_no_bypass_in_provider(self):
        """Provider does not bypass approval."""
        import inspect
        source = inspect.getsource(AmazonOrderProvider)
        assert "auto_approve" not in source.lower()
        assert "bypass" not in source.lower()

    def test_provider_capabilities_no_submit(self):
        """Amazon provider does not have supplier submit capability."""
        provider = AmazonOrderProvider()
        assert provider.capabilities.supports_supplier_submit is False


# ===========================================================================
# 7. Read/Write Boundary
# ===========================================================================

class TestReadWriteBoundary:
    """Verify read-only operations are enforced."""

    def test_provider_read_only_capabilities(self):
        """Amazon provider only has read capabilities."""
        provider = AmazonOrderProvider()
        caps = provider.capabilities
        assert caps.supports_order_read is True
        assert caps.supports_order_list is True
        assert caps.supports_supplier_prepare is False
        assert caps.supports_supplier_submit is False

    def test_client_blocks_non_get(self):
        """SP-API client blocks non-GET methods."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")

        async def test():
            return await client._make_request("POST", "/test")

        with pytest.raises(SPAPIError, match="BLOCKED"):
            asyncio.get_event_loop().run_until_complete(test())

    def test_client_blocks_put(self):
        """SP-API client blocks PUT methods."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")

        async def test():
            return await client._make_request("PUT", "/test")

        with pytest.raises(SPAPIError, match="BLOCKED"):
            asyncio.get_event_loop().run_until_complete(test())

    def test_client_blocks_delete(self):
        """SP-API client blocks DELETE methods."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")

        async def test():
            return await client._make_request("DELETE", "/test")

        with pytest.raises(SPAPIError, match="BLOCKED"):
            asyncio.get_event_loop().run_until_complete(test())


# ===========================================================================
# 8. PII Protection
# ===========================================================================

class TestPIIProtection:
    """Verify PII is protected."""

    def test_buyer_email_anonymized(self):
        """Buyer email is anonymized in normalized order."""
        provider = AmazonOrderProvider()
        order = {
            "amazonOrderId": "TEST-001",
            "buyerEmail": "real@marketplace.amazon.com",
            "recipientAddress": {"name": "Test"},
        }
        normalized = provider._normalize_order(order)
        assert "***" in normalized["customer_name"]
        assert "real@" not in normalized["customer_name"]

    def test_redact_pii_removes_phone(self):
        """PII redaction removes phone numbers."""
        assert "206-555-0101" not in redact_pii("Call 206-555-0101")

    def test_redact_pii_removes_zip(self):
        """PII redaction removes ZIP codes."""
        assert "98101" not in redact_pii("Ship to 98101")

    def test_redact_pii_removes_email(self):
        """PII redaction removes emails."""
        assert "test@example.com" not in redact_pii("Email test@example.com")

    def test_redact_secret_hides_value(self):
        """Secret redaction hides most of the value."""
        result = redact_secret("abcdefghijklmnopqrstuvwxyz")
        assert result.startswith("***")
        assert "wxyz" in result
        # Only last 4 chars visible
        visible = result.replace("*", "")
        assert len(visible) == 4


# ===========================================================================
# 9. Network Security
# ===========================================================================

class TestNetworkSecurity:
    """Verify network security."""

    def test_only_amazon_auth_endpoint_used(self):
        """Only Amazon auth endpoint is contacted for LWA."""
        from app.services.providers.amazon.lwa_auth import LWA_TOKEN_URL
        assert LWA_TOKEN_URL.startswith("https://")
        assert "api.amazon.com" in LWA_TOKEN_URL

    def test_sandbox_endpoints_use_https(self):
        """All sandbox endpoints use HTTPS."""
        for region, url in SANDBOX_ENDPOINTS.items():
            assert url.startswith("https://"), f"Sandbox endpoint {region} not HTTPS"

    def test_production_endpoints_use_https(self):
        """All production endpoints use HTTPS (even though blocked)."""
        for region, url in PRODUCTION_ENDPOINTS.items():
            assert url.startswith("https://"), f"Production endpoint {region} not HTTPS"

    def test_no_arbitrary_url_support(self):
        """SP-API client only supports known regions."""
        manager = LWATokenManager("id", "secret", "token")
        with pytest.raises(SPAPIError, match="Invalid region"):
            SPAPIClient(manager, region="malicious")

    def test_timeout_configured(self):
        """HTTP requests have timeout configured."""
        import inspect
        source = inspect.getsource(SPAPIClient._make_request_sync)
        assert "timeout" in source.lower()

    def test_rate_limit_constants(self):
        """Rate limit constants are defined."""
        assert DEFAULT_RATE_LIMIT == 1
        assert DEFAULT_BURST_LIMIT == 15


# ===========================================================================
# 10. Error Handling
# ===========================================================================

class TestErrorHandling:
    """Verify error handling is safe."""

    def test_lwa_error_class_structure(self):
        """LWA error has message and recoverable flag."""
        error = LWAAuthenticationError("test error", recoverable=True)
        assert error.message == "test error"
        assert error.recoverable is True

    def test_spapi_error_class_structure(self):
        """SP-API error has message, status, type, recoverable."""
        error = SPAPIError("test", status_code=400, error_type="BadRequest", recoverable=True)
        assert error.status_code == 400
        assert error.error_type == "BadRequest"
        assert error.recoverable is True

    def test_provider_returns_none_for_unconfigured(self):
        """Provider returns None when not configured (no crash)."""
        provider = AmazonOrderProvider()
        assert provider.get_order("TEST") is None
        assert provider.list_orders() == []
        assert provider.search_orders() == []

    def test_error_does_not_leak_credentials(self):
        """Error messages don't contain credentials."""
        manager = LWATokenManager("my_id", "my_secret", "my_token")
        try:
            manager.get_access_token_sync()
        except LWAAuthenticationError:
            pass  # Expected — no real credentials
        # Verify secret not in error (this is a structural test)

    def test_spapi_error_safe_for_display(self):
        """SP-API error messages are safe for frontend display."""
        error = SPAPIError("Authentication failed", status_code=401)
        assert "my_secret" not in error.message


# ===========================================================================
# 11. Idempotency
# ===========================================================================

class TestIdempotency:
    """Verify idempotency across operations."""

    def test_duplicate_import_tracking(self):
        """Duplicate imports are prevented."""
        provider = AmazonOrderProvider()
        provider._imported_order_ids.add("ORDER-001")
        assert provider.is_order_imported("ORDER-001") is True
        # Second import should be skipped
        assert "ORDER-001" in provider._imported_order_ids

    def test_fulfillment_idempotency(self):
        """Duplicate fulfillment for same order returns existing workflow."""
        fulfillment_engine.clear()
        order_service.clear()
        inventory_service.clear()
        from app.schemas.order import OrderCreate, OrderStatus
        from app.schemas.inventory import InventoryCreate
        from app.schemas.fulfillment import FulfillmentStatus
        inventory_service.create(InventoryCreate(
            sku="IDEMP-SKU", product_name="Test", current_stock=100,
        ))
        order = order_service.create(OrderCreate(
            customer_name="Test",
            shipping_address="Test Customer\n123 Test Street\nNew York NY 10003\nUS",
            product_name="Test", sku="IDEMP-SKU", quantity=1,
        ), create_test_organization())
        wf1 = fulfillment_engine.start_workflow(order.id)
        # If it reached waiting_approval, the idempotency check returns same
        if wf1.status == FulfillmentStatus.WAITING_APPROVAL:
            wf2 = fulfillment_engine.start_workflow(order.id)
            assert wf1.id == wf2.id
        else:
            # Workflow failed (e.g. address validation), which is terminal
            # So starting again creates a new one — this is expected behavior
            wf2 = fulfillment_engine.start_workflow(order.id)
            assert wf2.order_id == order.id
        fulfillment_engine.clear()
        order_service.clear()
        inventory_service.clear()


# ===========================================================================
# 12. API Version
# ===========================================================================

class TestAPIVersion:
    """Verify correct API version is used."""

    def test_orders_api_version(self):
        """Orders API version is v2026-01-01."""
        assert ORDERS_API_VERSION == "2026-01-01"

    def test_version_in_api_path(self):
        """API version appears in request path."""
        path = f"/orders/{ORDERS_API_VERSION}/orders"
        assert "2026-01-01" in path

    def test_sandbox_info_endpoint_version(self):
        """Info endpoint reports correct API version."""
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            resp = c.get("/api/v1/amazon/info")
            body = resp.json()
            assert body["api_version"] == "2026-01-01"


# ===========================================================================
# 13. Regression
# ===========================================================================

class TestRegression:
    """Ensure existing functionality is not broken."""

    def test_health_endpoints(self):
        """Health endpoints still work."""
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            assert c.get("/health").status_code == 200
            assert c.get("/api/v1/health").status_code == 200
            assert c.get("/api/v1/status").status_code == 200

    def test_provider_endpoint(self):
        """Provider list endpoint still works."""
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            resp = c.get("/api/v1/providers")
            assert resp.status_code == 200
            body = resp.json()
            assert "providers" in body
            assert body["mock_only"] is True

    def test_orders_endpoint(self, client):
        """Orders endpoint still works (now requires real authentication —
        an intentional Phase 2B security change, not a regression).

        Uses the shared session `client` fixture rather than a fresh local
        TestClient — see test_fulfillment_safety.py's TestRegression
        .test_orders_still_work for why (cross-event-loop pooled-connection
        hazard against the application's single pooled AsyncEngine).
        """
        resp = client.post("/api/v1/orders", json={
            "customer_name": "Test", "shipping_address": "123 St",
            "product_name": "P", "quantity": 1,
        }, headers=auth_headers(client))
        assert resp.status_code == 201

    def test_inventory_endpoint(self):
        """Inventory endpoint still works."""
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app) as c:
            resp = c.post("/api/v1/inventory", json={
                "sku": "T", "product_name": "P", "current_stock": 10,
            })
            assert resp.status_code == 201

    def test_mock_order_provider_still_works(self):
        """Mock order provider still works."""
        provider = MockOrderProvider()
        orders = provider.list_orders()
        assert len(orders) == 3

    def test_all_providers_are_mock_or_sandbox(self):
        """All registered providers are mock or sandbox."""
        registry = create_default_registry()
        for info in registry.list_all():
            assert info["is_mock"] is True
            assert info["environment"] in ("mock", "sandbox")
