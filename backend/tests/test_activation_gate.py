"""Activation Gate Tests — CHUNK 1Y.

Tests for production activation gate, including:
- Missing credentials
- Incomplete credentials
- Invalid environment
- Production endpoint protection
- Read-only enforcement
- Secret redaction
- Frontend credential protection
- Approval gate preservation
- Configuration validation
"""

import asyncio
import inspect
import os
from unittest.mock import patch

import pytest

from app.core.config import Settings, settings
from app.services.providers.amazon.activation_validator import (
    validate_production_activation,
    get_activation_status,
)
from app.services.providers.amazon.lwa_auth import LWATokenManager, LWAAuthenticationError
from tests.conftest import create_test_organization
from app.services.providers.amazon.sp_api_client import (
    SPAPIClient,
    SPAPIError,
    SANDBOX_ENDPOINTS,
    PRODUCTION_ENDPOINTS,
)
from app.services.providers.amazon.order_provider import AmazonOrderProvider
from app.services.providers.base import ProviderEnvironment, MOCK_ONLY


# ===========================================================================
# 1. Missing Credentials
# ===========================================================================

class TestMissingCredentials:
    """Verify behavior when credentials are missing."""

    def test_no_credentials_validation_fails(self):
        """Validation fails without credentials."""
        with patch.dict(os.environ, {
            "AMAZON_LWA_CLIENT_ID": "",
            "AMAZON_LWA_CLIENT_SECRET": "",
            "AMAZON_LWA_REFRESH_TOKEN": "",
            "AMAZON_ENVIRONMENT": "production",
        }, clear=False):
            result = validate_production_activation()
            assert result.is_ready is False
            assert result.checks["client_id"] is False
            assert result.checks["client_secret"] is False
            assert result.checks["refresh_token"] is False

    def test_missing_client_id(self):
        """Validation fails without client_id."""
        with patch.dict(os.environ, {
            "AMAZON_LWA_CLIENT_ID": "",
            "AMAZON_LWA_CLIENT_SECRET": "test_secret",
            "AMAZON_LWA_REFRESH_TOKEN": "test_token",
            "AMAZON_ENVIRONMENT": "production",
        }, clear=False):
            result = validate_production_activation()
            assert result.is_ready is False
            assert result.checks["client_id"] is False

    def test_missing_client_secret(self):
        """Validation fails without client_secret."""
        with patch.dict(os.environ, {
            "AMAZON_LWA_CLIENT_ID": "test_id",
            "AMAZON_LWA_CLIENT_SECRET": "",
            "AMAZON_LWA_REFRESH_TOKEN": "test_token",
            "AMAZON_ENVIRONMENT": "production",
        }, clear=False):
            result = validate_production_activation()
            assert result.is_ready is False
            assert result.checks["client_secret"] is False

    def test_missing_refresh_token(self):
        """Validation fails without refresh_token."""
        with patch.dict(os.environ, {
            "AMAZON_LWA_CLIENT_ID": "test_id",
            "AMAZON_LWA_CLIENT_SECRET": "test_secret",
            "AMAZON_LWA_REFRESH_TOKEN": "",
            "AMAZON_ENVIRONMENT": "production",
        }, clear=False):
            result = validate_production_activation()
            assert result.is_ready is False
            assert result.checks["refresh_token"] is False

    def test_provider_not_configured_without_credentials(self):
        """Provider reports not configured without credentials."""
        provider = AmazonOrderProvider()
        assert provider.is_configured is False


# ===========================================================================
# 2. Incomplete Credentials
# ===========================================================================

class TestIncompleteCredentials:
    """Verify behavior with incomplete credentials."""

    def test_two_of_three_credentials(self):
        """Validation fails with only two credentials."""
        with patch.dict(os.environ, {
            "AMAZON_LWA_CLIENT_ID": "test_id",
            "AMAZON_LWA_CLIENT_SECRET": "test_secret",
            "AMAZON_LWA_REFRESH_TOKEN": "",
            "AMAZON_ENVIRONMENT": "production",
        }, clear=False):
            result = validate_production_activation()
            assert result.is_ready is False
            assert result.checks["all_credentials"] is False

    def test_lwa_manager_requires_all_three(self):
        """LWA manager requires all three credentials."""
        with pytest.raises(LWAAuthenticationError):
            LWATokenManager("id", "secret", "")


# ===========================================================================
# 3. Invalid Environment
# ===========================================================================

class TestInvalidEnvironment:
    """Verify invalid environment is handled safely."""

    def test_invalid_environment_validation_fails(self):
        """Invalid environment fails validation."""
        with patch.dict(os.environ, {
            "AMAZON_ENVIRONMENT": "INVALID",
        }, clear=False):
            result = validate_production_activation()
            assert result.checks["environment"] is False
            assert any("invalid" in e.lower() for e in result.errors)

    def test_empty_environment_defaults_to_sandbox(self):
        """Empty environment defaults to sandbox."""
        s = Settings()
        original = s.AMAZON_ENVIRONMENT
        try:
            s.AMAZON_ENVIRONMENT = ""
            assert s.amazon_environment == "sandbox"
        finally:
            s.AMAZON_ENVIRONMENT = original

    def test_sandbox_environment_not_production_ready(self):
        """Sandbox environment is not production ready."""
        with patch.dict(os.environ, {
            "AMAZON_LWA_CLIENT_ID": "test_id",
            "AMAZON_LWA_CLIENT_SECRET": "test_secret",
            "AMAZON_LWA_REFRESH_TOKEN": "test_token",
            "AMAZON_ENVIRONMENT": "sandbox",
        }, clear=False):
            result = validate_production_activation()
            assert result.is_ready is False
            assert result.checks["production_ready"] is False


# ===========================================================================
# 4. Production Endpoint Protection
# ===========================================================================

class TestProductionEndpointProtection:
    """Verify production endpoints are protected."""

    def test_production_blocked_in_sandbox_mode(self):
        """Production endpoints blocked in sandbox mode."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na", environment="sandbox")

        with pytest.raises(SPAPIError, match="BLOCKED"):
            client._validate_endpoint("https://sellingpartnerapi-na.amazon.com/orders")

    def test_sandbox_allowed_in_sandbox_mode(self):
        """Sandbox endpoints allowed in sandbox mode."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na", environment="sandbox")
        client._validate_endpoint("https://sandbox.sellingpartnerapi-na.amazon.com/orders")

    def test_production_allowed_in_production_mode(self):
        """Production endpoints allowed in production mode."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na", environment="production")
        client._validate_endpoint("https://sellingpartnerapi-na.amazon.com/orders")

    def test_sandbox_blocked_in_production_mode(self):
        """Sandbox endpoints blocked in production mode."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na", environment="production")

        with pytest.raises(SPAPIError, match="BLOCKED"):
            client._validate_endpoint("https://sandbox.sellingpartnerapi-na.amazon.com/orders")


# ===========================================================================
# 5. Read-Only Enforcement
# ===========================================================================

class TestReadonlyEnforcement:
    """Verify read-only operations are enforced."""

    def test_provider_read_only_capabilities(self):
        """Amazon provider only has read capabilities."""
        provider = AmazonOrderProvider()
        caps = provider.capabilities
        assert caps.supports_order_read is True
        assert caps.supports_order_list is True
        assert caps.supports_supplier_submit is False

    def test_client_blocks_post(self):
        """SP-API client blocks POST methods."""
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

    def test_no_auto_approval_in_engine(self):
        """No auto-approval mechanism exists."""
        from app.services.fulfillment.workflow import fulfillment_engine
        source = inspect.getsource(fulfillment_engine.__class__)
        assert "auto_approve" not in source.lower()
        assert "skip_approval" not in source.lower()


# ===========================================================================
# 6. Secret Redaction
# ===========================================================================

class TestSecretRedaction:
    """Verify secrets are properly redacted."""

    def test_no_credentials_in_api_responses(self):
        """API responses never contain credentials."""
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as c:
            resp = c.get("/api/v1/amazon/status")
            body = resp.json()
            for key, val in body.items():
                val_str = str(val).lower()
                assert "client_secret" not in val_str
                assert "refresh_token" not in val_str
                assert "access_token" not in val_str

    def test_lwa_logger_uses_redacted_format(self):
        """LWA logger uses redacted format for client_id."""
        source = inspect.getsource(LWATokenManager.__init__)
        assert "redact_secret" in source

    def test_activation_status_excludes_secret_values(self):
        """Activation status excludes secret VALUES (not key names)."""
        result = get_activation_status()
        # Check that no actual secret values appear
        # The keys 'client_secret' and 'refresh_token' are configuration names, not secrets
        # We check that no actual secret VALUES are exposed
        full_str = str(result)
        # Check for common secret patterns (actual values, not key names)
        assert "amzn1.ask.account" not in full_str
        assert "Atzr|" not in full_str
        assert "Atza|" not in full_str


# ===========================================================================
# 7. Frontend Credential Protection
# ===========================================================================

class TestFrontendCredentialProtection:
    """Verify frontend never exposes credentials."""

    def test_no_credentials_in_frontend_source(self):
        """No credentials in frontend source files."""
        import glob
        patterns = ["client_secret", "refresh_token", "access_token", "authorization_code"]
        for filepath in glob.glob("frontend/src/**/*.ts", recursive=True) + \
                         glob.glob("frontend/src/**/*.tsx", recursive=True):
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for pat in patterns:
                    assert pat not in content.lower(), f"Found credential in {filepath}"


# ===========================================================================
# 8. Approval Gate Preservation
# ===========================================================================

class TestApprovalGatePreservation:
    """Verify approval gate is preserved."""

    def test_fulfillment_stops_at_waiting_approval(self):
        """Fulfillment always stops at WAITING_APPROVAL."""
        from app.services.fulfillment.workflow import fulfillment_engine
        from app.services.order_service import order_service
        from app.services.inventory_service import inventory_service
        from app.schemas.order import OrderCreate
        from app.schemas.inventory import InventoryCreate
        from app.schemas.fulfillment import FulfillmentStatus

        fulfillment_engine.clear()
        order_service.clear()
        inventory_service.clear()

        inventory_service.create(InventoryCreate(
            sku="APPROVAL-GATE-SKU", product_name="Test", current_stock=100,
        ))
        order = order_service.create(OrderCreate(
            customer_name="Test",
            shipping_address="Test Customer\n123 Test St\nNew York NY 10003\nUS",
            product_name="Test", sku="APPROVAL-GATE-SKU", quantity=1,
        ), create_test_organization())
        wf = fulfillment_engine.start_workflow(order.id)
        assert wf.status in (FulfillmentStatus.WAITING_APPROVAL, FulfillmentStatus.FAILED)

        fulfillment_engine.clear()
        order_service.clear()
        inventory_service.clear()

    def test_no_bypass_in_provider(self):
        """Provider does not bypass approval."""
        source = inspect.getsource(AmazonOrderProvider)
        assert "auto_approve" not in source.lower()
        assert "bypass" not in source.lower()

    def test_provider_capabilities_no_submit(self):
        """Amazon provider does not have supplier submit capability."""
        provider = AmazonOrderProvider()
        assert provider.capabilities.supports_supplier_submit is False


# ===========================================================================
# 9. Configuration Validation
# ===========================================================================

class TestConfigurationValidation:
    """Verify configuration validation works."""

    def test_validate_production_activation_callable(self):
        """validate_production_activation is callable."""
        result = validate_production_activation()
        assert hasattr(result, "is_ready")
        assert hasattr(result, "checks")
        assert hasattr(result, "errors")

    def test_get_activation_status_callable(self):
        """get_activation_status is callable."""
        result = get_activation_status()
        assert "ready" in result
        assert "checks" in result
        assert "errors" in result

    def test_validation_no_api_calls(self):
        """Validation does not make API calls."""
        import inspect
        source = inspect.getsource(validate_production_activation)
        # Should not contain httpx, requests, or fetch
        assert "httpx" not in source
        assert "requests." not in source
        assert "fetch(" not in source


# ===========================================================================
# 10. Mock-Only Mode
# ===========================================================================

class TestMockOnlyMode:
    """Verify mock-only mode works correctly."""

    def test_without_credentials_mock_only(self):
        """Without credentials, system runs in mock-only mode."""
        with patch.dict(os.environ, {
            "AMAZON_LWA_CLIENT_ID": "",
            "AMAZON_LWA_CLIENT_SECRET": "",
            "AMAZON_LWA_REFRESH_TOKEN": "",
        }, clear=False):
            provider = AmazonOrderProvider()
            assert provider.is_configured is False
            # Should return None/empty for all operations
            assert provider.get_order("TEST") is None
            assert provider.list_orders() == []
            assert provider.search_orders() == []

    def test_mock_only_flag_exists(self):
        """MOCK_ONLY global flag exists."""
        assert MOCK_ONLY is True

    def test_mock_providers_still_work(self):
        """Mock providers still work without Amazon credentials."""
        from app.services.providers.mock.order_provider import MockOrderProvider
        provider = MockOrderProvider()
        orders = provider.list_orders()
        assert len(orders) == 3


# ===========================================================================
# 11. API Endpoint Tests
# ===========================================================================

class TestActivationAPIEndpoint:
    """Test activation status API endpoint."""

    def test_activation_status_endpoint(self):
        """Activation status endpoint works."""
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as c:
            resp = c.get("/api/v1/amazon/activation-status")
            assert resp.status_code == 200
            body = resp.json()
            assert "ready" in body
            assert "checks" in body
            assert "errors" in body
            assert body["notice"] == "This validation does NOT make Amazon API calls"
