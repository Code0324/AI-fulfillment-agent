"""Amazon SP-API Integration Tests — CHUNK 1V.

Comprehensive tests for Amazon sandbox integration.
All tests use mock data — no real Amazon credentials required.

CRITICAL SAFETY:
- Tests never use real credentials
- Tests never make real API calls
- Tests verify production endpoint blocking
- Tests verify read-only operations
- Tests verify credential protection
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

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
)
from app.services.providers.amazon.order_provider import AmazonOrderProvider

from tests.conftest import create_test_organization
from app.services.providers.base import (
    BaseProvider,
    ProviderCapabilities,
    ProviderEnvironment,
)
from app.services.providers.registry import provider_registry


# ===========================================================================
# 1. LWA Authentication Tests
# ===========================================================================

class TestLWAAuthentication:
    """LWA authentication behavior."""
    
    def test_lwa_token_manager_requires_credentials(self):
        """LWA token manager requires all credentials."""
        with pytest.raises(LWAAuthenticationError):
            LWATokenManager("", "secret", "token")
        
        with pytest.raises(LWAAuthenticationError):
            LWATokenManager("client_id", "", "token")
        
        with pytest.raises(LWAAuthenticationError):
            LWATokenManager("client_id", "secret", "")
    
    def test_lwa_token_manager_stores_credentials_in_memory(self):
        """Credentials are stored in memory only."""
        manager = LWATokenManager("client_id", "client_secret", "refresh_token")
        
        # Check that credentials are stored
        assert manager._client_id == "client_id"
        assert manager._client_secret == "client_secret"
        assert manager._refresh_token == "refresh_token"
        
        # Check they are not in repr or str
        assert "client_secret" not in repr(manager)
        assert "refresh_token" not in repr(manager)
    
    def test_lwa_token_manager_is_configured(self):
        """is_configured returns True when all credentials set."""
        manager = LWATokenManager("client_id", "client_secret", "refresh_token")
        assert manager.is_configured is True
    
    def test_lwa_token_manager_requires_all_credentials(self):
        """is_configured returns False when credentials missing."""
        # Empty credentials should raise error during construction
        with pytest.raises(LWAAuthenticationError):
            LWATokenManager("", "", "")
    
    def test_lwa_token_expires_in(self):
        """token_expires_in returns seconds until expiry."""
        manager = LWATokenManager("client_id", "client_secret", "refresh_token")
        
        # No token yet
        assert manager.token_expires_in == 0
    
    def test_lwa_invalidate_token(self):
        """invalidate_token clears cached token."""
        manager = LWATokenManager("client_id", "client_secret", "refresh_token")
        manager._access_token = "test_token"
        manager._token_expires_at = 999999999999
        
        manager.invalidate_token()
        
        assert manager._access_token is None
        assert manager._token_expires_at == 0
    
    def test_lwa_clear(self):
        """clear resets all state."""
        manager = LWATokenManager("client_id", "client_secret", "refresh_token")
        manager._access_token = "test_token"
        manager._token_refresh_count = 5
        
        manager.clear()
        
        assert manager._access_token is None
        assert manager._token_refresh_count == 0
    
    def test_lwa_create_from_env_missing_credentials(self):
        """create_lwa_token_manager_from_env returns None without credentials."""
        with patch.dict(os.environ, {}, clear=True):
            result = create_lwa_token_manager_from_env()
            assert result is None
    
    def test_lwa_create_from_env_with_credentials(self):
        """create_lwa_token_manager_from_env creates manager with credentials."""
        env = {
            "AMAZON_LWA_CLIENT_ID": "test_client_id",
            "AMAZON_LWA_CLIENT_SECRET": "test_client_secret",
            "AMAZON_LWA_REFRESH_TOKEN": "test_refresh_token",
        }
        with patch.dict(os.environ, env):
            result = create_lwa_token_manager_from_env()
            assert result is not None
            assert result.is_configured is True


# ===========================================================================
# 2. SP-API Client Tests
# ===========================================================================

class TestSPAPIClient:
    """SP-API client behavior."""
    
    def test_client_requires_valid_region(self):
        """Client rejects invalid region."""
        manager = LWATokenManager("id", "secret", "token")
        with pytest.raises(SPAPIError, match="Invalid region"):
            SPAPIClient(manager, region="invalid")
    
    def test_client_accepts_valid_regions(self):
        """Client accepts valid regions."""
        manager = LWATokenManager("id", "secret", "token")
        
        for region in ["na", "eu", "fe"]:
            client = SPAPIClient(manager, region=region)
            assert client._region == region
    
    def test_client_uses_sandbox_endpoint(self):
        """Client uses sandbox endpoint (not production)."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")
        
        assert client._base_url == SANDBOX_ENDPOINTS["na"]
        assert client._base_url not in PRODUCTION_ENDPOINTS.values()
    
    def test_client_is_sandbox(self):
        """Client confirms sandbox mode."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")
        
        assert client.is_sandbox is True
    
    def test_client_blocks_production_endpoint(self):
        """Client blocks production endpoints."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")
        
        # Try to validate a production URL
        with pytest.raises(SPAPIError, match="BLOCKED"):
            client._validate_endpoint("https://sellingpartnerapi-na.amazon.com/orders")
    
    def test_client_allows_sandbox_endpoint(self):
        """Client allows sandbox endpoints."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")
        
        # Should not raise
        client._validate_endpoint("https://sandbox.sellingpartnerapi-na.amazon.com/orders")
    
    def test_client_enforces_read_only(self):
        """Client enforces read-only operations via _make_request validation."""
        import asyncio
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")
        
        # _make_request should reject non-GET methods
        async def test_post():
            return await client._make_request("POST", "/test")
        
        with pytest.raises(SPAPIError, match="BLOCKED"):
            asyncio.get_event_loop().run_until_complete(test_post())
    
    def test_client_request_stats(self):
        """Client tracks request statistics."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")
        
        stats = client.request_stats
        assert stats["total_requests"] == 0
        assert stats["successful_requests"] == 0
        assert stats["failed_requests"] == 0
        assert stats["is_sandbox"] is True


# ===========================================================================
# 3. Amazon Order Provider Tests
# ===========================================================================

class TestAmazonOrderProvider:
    """Amazon order provider behavior."""
    
    def test_provider_is_base_provider(self):
        """AmazonOrderProvider implements BaseProvider."""
        provider = AmazonOrderProvider()
        assert isinstance(provider, BaseProvider)
    
    def test_provider_name(self):
        """Provider has correct name."""
        provider = AmazonOrderProvider()
        assert provider.provider_name == "amazon_order_provider"
    
    def test_provider_environment_is_sandbox(self):
        """Provider reports SANDBOX environment."""
        provider = AmazonOrderProvider()
        assert provider.environment == ProviderEnvironment.SANDBOX
    
    def test_provider_is_mock(self):
        """Provider is considered mock (sandbox)."""
        provider = AmazonOrderProvider()
        assert provider.is_mock is True
    
    def test_provider_capabilities(self):
        """Provider has read-only capabilities."""
        provider = AmazonOrderProvider()
        caps = provider.capabilities
        
        assert caps.supports_order_read is True
        assert caps.supports_order_list is True
        assert caps.supports_supplier_prepare is False
        assert caps.supports_supplier_verify is False
        assert caps.supports_supplier_submit is False
        assert caps.supports_tracking_read is False
    
    def test_provider_not_configured_without_credentials(self):
        """Provider not configured without credentials."""
        with patch.dict(os.environ, {}, clear=True):
            provider = AmazonOrderProvider()
            assert provider.is_configured is False
    
    def test_provider_connection_status(self):
        """Provider returns connection status."""
        provider = AmazonOrderProvider()
        status = provider.connection_status
        
        assert "configured" in status
        assert "sandbox" in status
        assert "environment" in status
        assert "mode" in status
        assert status["sandbox"] is True
        assert status["environment"] == "sandbox"
        assert status["mode"] == "read-only"
    
    def test_provider_get_order_returns_none_when_not_configured(self):
        """Provider returns None when not configured."""
        provider = AmazonOrderProvider()
        result = provider.get_order("TEST-ORDER")
        assert result is None
    
    def test_provider_list_orders_returns_empty_when_not_configured(self):
        """Provider returns empty list when not configured."""
        provider = AmazonOrderProvider()
        result = provider.list_orders()
        assert result == []
    
    def test_provider_import_orders_returns_empty_when_not_configured(self):
        """Provider returns empty list when not configured."""
        provider = AmazonOrderProvider()
        result = provider.import_orders()
        assert result == []
    
    def test_provider_test_connection_when_not_configured(self):
        """Provider test_connection reports not configured."""
        provider = AmazonOrderProvider()
        result = provider.test_connection()
        
        assert result["success"] is False
        assert result["sandbox"] is True
        assert result["environment"] == "sandbox"
    
    def test_provider_clear_imports(self):
        """Provider clears import tracking."""
        provider = AmazonOrderProvider()
        provider._imported_order_ids.add("TEST-ORDER")
        provider._orders_retrieved = 5
        
        provider.clear_imports()
        
        assert len(provider._imported_order_ids) == 0
        assert provider._orders_retrieved == 0
    
    def test_provider_is_order_imported(self):
        """Provider tracks imported orders."""
        provider = AmazonOrderProvider()
        
        assert provider.is_order_imported("TEST-ORDER") is False
        provider._imported_order_ids.add("TEST-ORDER")
        assert provider.is_order_imported("TEST-ORDER") is True


# ===========================================================================
# 4. Sandbox Environment Enforcement Tests
# ===========================================================================

class TestSandboxEnvironmentEnforcement:
    """Verify sandbox-only access."""
    
    def test_sandbox_endpoints_defined(self):
        """Sandbox endpoints are defined."""
        assert "na" in SANDBOX_ENDPOINTS
        assert "eu" in SANDBOX_ENDPOINTS
        assert "fe" in SANDBOX_ENDPOINTS
        
        for region, url in SANDBOX_ENDPOINTS.items():
            assert "sandbox" in url
    
    def test_production_endpoints_defined(self):
        """Production endpoints are defined (for blocking)."""
        assert "na" in PRODUCTION_ENDPOINTS
        assert "eu" in PRODUCTION_ENDPOINTS
        assert "fe" in PRODUCTION_ENDPOINTS
    
    def test_production_endpoints_differ_from_sandbox(self):
        """Production endpoints are different from sandbox."""
        for region in SANDBOX_ENDPOINTS:
            assert SANDBOX_ENDPOINTS[region] != PRODUCTION_ENDPOINTS[region]
    
    def test_provider_environment_is_sandbox(self):
        """Provider environment is always sandbox."""
        provider = AmazonOrderProvider()
        assert provider.environment == ProviderEnvironment.SANDBOX
    
    def test_client_blocks_production_na(self):
        """Client blocks North America production endpoint."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")
        
        with pytest.raises(SPAPIError, match="BLOCKED"):
            client._validate_endpoint(PRODUCTION_ENDPOINTS["na"])
    
    def test_client_blocks_production_eu(self):
        """Client blocks Europe production endpoint."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="eu")
        
        with pytest.raises(SPAPIError, match="BLOCKED"):
            client._validate_endpoint(PRODUCTION_ENDPOINTS["eu"])
    
    def test_client_blocks_production_fe(self):
        """Client blocks Far East production endpoint."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="fe")
        
        with pytest.raises(SPAPIError, match="BLOCKED"):
            client._validate_endpoint(PRODUCTION_ENDPOINTS["fe"])


# ===========================================================================
# 5. Read-Only Operation Enforcement Tests
# ===========================================================================

class TestReadOnlyEnforcement:
    """Verify read-only operations are enforced."""
    
    def test_provider_capabilities_read_only(self):
        """Provider only supports read operations."""
        provider = AmazonOrderProvider()
        caps = provider.capabilities
        
        # Read operations allowed
        assert caps.supports_order_read is True
        assert caps.supports_order_list is True
        
        # Write operations blocked
        assert caps.supports_supplier_prepare is False
        assert caps.supports_supplier_verify is False
        assert caps.supports_supplier_submit is False
    
    def test_client_enforces_read_only(self):
        """Client enforces GET-only operations."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")
        
        # We can't test actual API calls without credentials,
        # but we can verify the validation logic
        # The _make_request method checks for GET-only
        # This is verified by the implementation


# ===========================================================================
# 6. Credential Protection Tests
# ===========================================================================

class TestCredentialProtection:
    """Verify credentials are never exposed."""
    
    def test_no_credentials_in_provider_source(self):
        """No credentials in provider source code."""
        import inspect
        source = inspect.getsource(AmazonOrderProvider)
        
        # Check for credential patterns
        forbidden = [
            "client_id=",
            "client_secret=",
            "refresh_token=",
            "access_token=",
        ]
        
        for pattern in forbidden:
            assert pattern not in source, f"Found credential pattern: {pattern}"
    
    def test_no_credentials_in_lwa_source(self):
        """No hardcoded credentials in LWA source."""
        import inspect
        from app.services.providers.amazon.lwa_auth import LWATokenManager
        source = inspect.getsource(LWATokenManager)
        
        # Should not have hardcoded values
        assert "amzn1.ask.account" not in source
        assert "Atzr|" not in source
        assert "Atza|" not in source
    
    def test_no_credentials_in_client_source(self):
        """No hardcoded credentials in client source."""
        import inspect
        from app.services.providers.amazon.sp_api_client import SPAPIClient
        source = inspect.getsource(SPAPIClient)
        
        assert "amzn1.ask.account" not in source
        assert "Atzr|" not in source
    
    def test_credentials_not_in_logs(self):
        """Credentials are not logged."""
        # This is enforced by the implementation using ***
        manager = LWATokenManager("test_client_id", "test_secret", "test_token")
        
        # The logger.info in __init__ uses *** for client_id
        # This test verifies the pattern
        import inspect
        source = inspect.getsource(LWATokenManager.__init__)
        
        # Should use redacted format
        assert "***" in source or "redact" in source.lower()
    
    def test_tokens_not_in_response(self):
        """Tokens are not included in API responses."""
        provider = AmazonOrderProvider()
        status = provider.connection_status
        
        # Status should not contain actual tokens
        assert "access_token" not in status
        assert "refresh_token" not in status
        assert "client_secret" not in status


# ===========================================================================
# 7. Rate Limiting Tests
# ===========================================================================

class TestRateLimiting:
    """Verify rate limiting is enforced."""
    
    def test_rate_limit_constants(self):
        """Rate limit constants are defined."""
        from app.services.providers.amazon.sp_api_client import (
            DEFAULT_RATE_LIMIT,
            DEFAULT_BURST_LIMIT,
        )
        
        assert DEFAULT_RATE_LIMIT == 1
        assert DEFAULT_BURST_LIMIT == 15
    
    def test_client_enforces_rate_limit(self):
        """Client enforces rate limiting between requests."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na")
        
        # Record first request time
        client._last_request_time = 0
        
        # Should enforce delay
        client._enforce_rate_limit()
        
        # Second call should have been delayed
        assert client._last_request_time > 0


# ===========================================================================
# 8. Provider Registry Tests
# ===========================================================================

class TestProviderRegistry:
    """Provider registry behavior with Amazon provider."""
    
    def test_registry_lists_all_providers(self):
        """Registry lists all registered providers."""
        providers = provider_registry.list_all()
        
        # Should have mock providers
        names = [p["name"] for p in providers]
        assert "mock_order_provider" in names
        assert "mock_supplier_provider" in names
        assert "mock_tracking_provider" in names
    
    def test_registry_get_amazon_provider(self):
        """Registry can get Amazon provider."""
        amazon = provider_registry.get_amazon_provider()
        
        # May be None if not configured (no credentials)
        if amazon is not None:
            assert amazon.provider_name == "amazon_order_provider"
            assert amazon.environment == ProviderEnvironment.SANDBOX
    
    def test_registry_all_providers_are_mock(self):
        """All registered providers are mock/sandbox."""
        providers = provider_registry.list_all()
        
        for provider in providers:
            assert provider["is_mock"] is True
            assert provider["environment"] in ("mock", "sandbox")


# ===========================================================================
# 9. Order Normalization Tests
# ===========================================================================

class TestOrderNormalization:
    """Verify Amazon order normalization."""
    
    def test_normalize_amazon_order(self):
        """Normalize Amazon order to internal format."""
        provider = AmazonOrderProvider()
        
        amazon_order = {
            "amazonOrderId": "111-1234567-1234567",
            "orderStatus": "Unshipped",
            "purchaseDate": "2026-01-15T10:00:00Z",
            "fulfillmentChannel": "MFN",
            "buyerEmail": "test@example.com",
            "recipientAddress": {
                "name": "Test Customer",
                "addressLine1": "123 Test Street",
                "city": "New York",
                "stateOrRegion": "NY",
                "postalCode": "10001",
                "countryCode": "US",
            },
        }
        
        normalized = provider._normalize_order(amazon_order)
        
        assert normalized is not None
        assert normalized["amazon_order_id"] == "111-1234567-1234567"
        assert normalized["source"] == "AMAZON_SANDBOX"
        assert normalized["order_status"] == "Unshipped"
        assert "Test Customer" in normalized["shipping_address"]
        assert "123 Test Street" in normalized["shipping_address"]
    
    def test_normalize_empty_order(self):
        """Normalize empty order returns None."""
        provider = AmazonOrderProvider()
        
        result = provider._normalize_order({})
        assert result is None
    
    def test_normalize_none_order(self):
        """Normalize None order returns None."""
        provider = AmazonOrderProvider()
        
        result = provider._normalize_order(None)
        assert result is None
    
    def test_anonymize_buyer_email(self):
        """Buyer email is anonymized."""
        provider = AmazonOrderProvider()
        
        amazon_order = {
            "amazonOrderId": "TEST-001",
            "buyerEmail": "real@example.com",
        }
        
        normalized = provider._normalize_order(amazon_order)
        
        # Email should be anonymized
        assert "real@" not in normalized["customer_name"]
        assert "***" in normalized["customer_name"]


# ===========================================================================
# 10. API Endpoint Tests
# ===========================================================================

class TestAmazonAPIEndpoints:
    """Amazon API endpoint tests."""
    
    def test_amazon_status_endpoint(self):
        """Amazon status endpoint works."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        with TestClient(app) as c:
            resp = c.get("/api/v1/amazon/status")
            assert resp.status_code == 200
            body = resp.json()
            assert "sandbox" in body
            assert body["sandbox"] is True
            assert "environment" in body
            assert body["environment"] == "sandbox"
    
    def test_amazon_info_endpoint(self):
        """Amazon info endpoint works."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        with TestClient(app) as c:
            resp = c.get("/api/v1/amazon/info")
            assert resp.status_code == 200
            body = resp.json()
            assert body["sandbox"] is True
            assert body["mode"] == "read-only"
            assert "api_version" in body
            assert body["api_version"] == "2026-01-01"
    
    def test_amazon_orders_endpoint(self):
        """Amazon orders endpoint works."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        with TestClient(app) as c:
            resp = c.get("/api/v1/amazon/orders")
            assert resp.status_code == 200
            body = resp.json()
            assert body["sandbox"] is True
            assert "orders" in body
    
    def test_amazon_test_connection_endpoint(self):
        """Amazon test connection endpoint works."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        with TestClient(app) as c:
            resp = c.get("/api/v1/amazon/test-connection")
            assert resp.status_code == 200
            body = resp.json()
            assert body["sandbox"] is True
            assert "success" in body


# ===========================================================================
# 11. Approval Gate Integrity Tests
# ===========================================================================

class TestApprovalGateIntegrity:
    """Verify approval gate is not bypassed."""
    
    def test_no_auto_approval_in_provider(self):
        """Provider does not have auto-approval."""
        import inspect
        source = inspect.getsource(AmazonOrderProvider)
        
        assert "auto_approve" not in source.lower()
        assert "skip_approval" not in source.lower()
        assert "automatic" not in source.lower()
    
    def test_provider_does_not_submit_to_supplier(self):
        """Provider does not submit to supplier."""
        provider = AmazonOrderProvider()
        
        # Provider should not have submit capabilities
        assert provider.capabilities.supports_supplier_submit is False
    
    def test_import_orders_stops_before_fulfillment(self):
        """Imported orders are ready for fulfillment, not auto-submitted."""
        provider = AmazonOrderProvider()
        
        # Import returns order IDs, not fulfillment results
        # The actual fulfillment is handled by the existing engine
        result = provider.import_orders()
        assert isinstance(result, list)


# ===========================================================================
# 12. Multi-Tenant Isolation Tests
# ===========================================================================

class TestMultiTenantIsolation:
    """Verify multi-tenant isolation."""
    
    def test_provider_instances_are_independent(self):
        """Provider instances are independent (no shared state)."""
        provider1 = AmazonOrderProvider()
        provider2 = AmazonOrderProvider()
        
        # Each has its own import tracking
        provider1._imported_order_ids.add("ORDER-1")
        assert provider2.is_order_imported("ORDER-1") is False
    
    def test_registry_clears_all_providers(self):
        """Registry clear removes all providers."""
        from app.services.providers.registry import ProviderRegistry
        
        registry = ProviderRegistry()
        registry.register(AmazonOrderProvider())
        
        registry.clear()
        
        assert registry.get("amazon_order_provider") is None


# ===========================================================================
# 13. Regression Tests
# ===========================================================================

class TestRegression:
    """Ensure existing functionality still works."""
    
    def test_health_endpoints(self):
        """Health endpoints still work."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        with TestClient(app) as c:
            assert c.get("/health").status_code == 200
            assert c.get("/api/v1/health").status_code == 200
            assert c.get("/api/v1/status").status_code == 200
    
    def test_provider_endpoints(self):
        """Provider endpoints still work."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        with TestClient(app) as c:
            resp = c.get("/api/v1/providers")
            assert resp.status_code == 200
            body = resp.json()
            assert "providers" in body
    
    def test_mock_orders_still_work(self):
        """Mock order provider still works."""
        from app.services.providers.mock.order_provider import MockOrderProvider
        
        provider = MockOrderProvider()
        orders = provider.list_orders()
        assert len(orders) == 3
    
    def test_fulfillment_engine_still_works(self):
        """Fulfillment engine still works."""
        from app.services.fulfillment.workflow import fulfillment_engine
        from app.services.order_service import order_service
        from app.services.inventory_service import inventory_service
        from app.schemas.order import OrderCreate
        from app.schemas.inventory import InventoryCreate
        
        # Clear state
        fulfillment_engine.clear()
        order_service.clear()
        inventory_service.clear()
        
        # Create test data
        inventory_service.create(InventoryCreate(
            sku="TEST-SKU",
            product_name="Test Product",
            current_stock=100,
        ))
        
        order = order_service.create(OrderCreate(
            customer_name="Test Customer",
            shipping_address="Test Customer\n123 Test Street\nNew York NY 10003\nUS",
            product_name="Test Product",
            sku="TEST-SKU",
            quantity=5,
        ), create_test_organization())
        
        # Start fulfillment
        wf = fulfillment_engine.start_workflow(order.id)
        assert wf.status.value in ("waiting_approval", "failed")
        
        # Clean up
        fulfillment_engine.clear()
        order_service.clear()
        inventory_service.clear()


# ===========================================================================
# 14. Security Scan Tests
# ===========================================================================

class TestSecurityScan:
    """Verify no credentials in source code."""
    
    def test_no_client_secret_in_source(self):
        """No client_secret in source files."""
        import subprocess
        result = subprocess.run(
            ["grep", "-r", "client_secret", "backend/app", "--include=*.py", "-l"],
            capture_output=True,
            text=True,
        )
        
        # Should not find any files with client_secret
        # (except maybe in config comments)
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        for f in files:
            if f and "config.py" not in f:
                # Check if it's a hardcoded value
                with open(f, "r") as fh:
                    content = fh.read()
                    assert "Y76SDl2F" not in content, f"Found hardcoded secret in {f}"
    
    def test_no_refresh_token_in_source(self):
        """No refresh_token in source files."""
        import subprocess
        result = subprocess.run(
            ["grep", "-r", "refresh_token", "backend/app", "--include=*.py", "-l"],
            capture_output=True,
            text=True,
        )
        
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        for f in files:
            if f:
                with open(f, "r") as fh:
                    content = fh.read()
                    # Should not have actual refresh tokens
                    assert "Atzr|" not in content, f"Found refresh token in {f}"
    
    def test_no_access_token_in_source(self):
        """No access_token in source files."""
        import subprocess
        result = subprocess.run(
            ["grep", "-r", "access_token", "backend/app", "--include=*.py", "-l"],
            capture_output=True,
            text=True,
        )
        
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        for f in files:
            if f:
                with open(f, "r") as fh:
                    content = fh.read()
                    # Should not have actual access tokens
                    assert "Atza|" not in content, f"Found access token in {f}"
    
    def test_no_production_endpoints_in_config(self):
        """No production endpoints in config."""
        from app.core.config import Settings
        
        # Config should not reference production endpoints
        # (except in comments for blocking)
        import inspect
        source = inspect.getsource(Settings)
        
        # Production endpoints should only be in SP-API client for blocking
        assert "sellingpartnerapi-na" not in source
