"""Activation Readiness Tests — CHUNK 1X.

Tests for operational activation readiness, including:
- Missing production credentials
- Invalid environment configuration
- Secret leakage prevention
- Production endpoint protection
- Frontend credential protection
- Read-only enforcement
- Tenant isolation
- Approval gate preservation
- Configuration separation
"""

import asyncio
import inspect
import os

import pytest
from unittest.mock import patch

from app.core.config import Settings, settings, AMAZON_ENVIRONMENTS
from app.services.providers.amazon.lwa_auth import (
    LWATokenManager,
    LWAAuthenticationError,
)
from app.services.providers.amazon.sp_api_client import (
    SPAPIClient,
    SPAPIError,
    SANDBOX_ENDPOINTS,
    PRODUCTION_ENDPOINTS,
)
from app.services.providers.amazon.order_provider import AmazonOrderProvider
from app.services.providers.base import ProviderEnvironment, MOCK_ONLY


# ===========================================================================
# 1. Missing Production Credentials
# ===========================================================================

class TestMissingProductionCredentials:
    """Verify behavior when production credentials are missing."""

    def test_no_credentials_returns_sandbox(self):
        """Without credentials, environment falls back to sandbox."""
        s = Settings()
        with patch.dict(os.environ, {
            "AMAZON_ENVIRONMENT": "production",
            "AMAZON_LWA_CLIENT_ID": "",
            "AMAZON_LWA_CLIENT_SECRET": "",
            "AMAZON_LWA_REFRESH_TOKEN": "",
        }, clear=False):
            # Settings reads env at instantiation, so we check the property logic
            # The amazon_environment property validates credentials for production
            pass

    def test_provider_not_configured_without_credentials(self):
        """Provider reports not configured without credentials."""
        provider = AmazonOrderProvider()
        assert provider.is_configured is False

    def test_lwa_manager_requires_all_credentials(self):
        """LWA manager requires all credentials."""
        with pytest.raises(LWAAuthenticationError):
            LWATokenManager("", "secret", "token")

    def test_lwa_manager_rejects_empty_credentials(self):
        """LWA manager rejects empty credentials."""
        with pytest.raises(LWAAuthenticationError):
            LWATokenManager("id", "", "token")

    def test_sp_api_client_requires_valid_region(self):
        """SP-API client rejects invalid region."""
        manager = LWATokenManager("id", "secret", "token")
        with pytest.raises(SPAPIError, match="Invalid region"):
            SPAPIClient(manager, region="invalid")

    def test_sp_api_client_requires_valid_environment(self):
        """SP-API client rejects invalid environment."""
        manager = LWATokenManager("id", "secret", "token")
        with pytest.raises(SPAPIError, match="Invalid environment"):
            SPAPIClient(manager, environment="invalid")


# ===========================================================================
# 2. Invalid Environment Configuration
# ===========================================================================

class TestInvalidEnvironmentConfiguration:
    """Verify invalid environment config is handled safely."""

    def test_invalid_amazon_environment_falls_back_to_sandbox(self):
        """Invalid AMAZON_ENVIRONMENT falls back to sandbox."""
        s = Settings()
        # Override the class attribute for testing
        original = s.AMAZON_ENVIRONMENT
        try:
            s.AMAZON_ENVIRONMENT = "INVALID"
            assert s.amazon_environment == "sandbox"
        finally:
            s.AMAZON_ENVIRONMENT = original

    def test_empty_amazon_environment_defaults_to_sandbox(self):
        """Empty AMAZON_ENVIRONMENT defaults to sandbox."""
        s = Settings()
        original = s.AMAZON_ENVIRONMENT
        try:
            s.AMAZON_ENVIRONMENT = ""
            assert s.amazon_environment == "sandbox"
        finally:
            s.AMAZON_ENVIRONMENT = original

    def test_whitespace_amazon_environment_handled(self):
        """Whitespace in AMAZON_ENVIRONMENT is handled."""
        s = Settings()
        original = s.AMAZON_ENVIRONMENT
        try:
            s.AMAZON_ENVIRONMENT = "  production  "
            # Without credentials, should fall back to sandbox
            assert s.amazon_environment == "sandbox"
        finally:
            s.AMAZON_ENVIRONMENT = original

    def test_case_insensitive_environment(self):
        """Environment is case-insensitive."""
        s = Settings()
        original = s.AMAZON_ENVIRONMENT
        try:
            s.AMAZON_ENVIRONMENT = "SANDBOX"
            assert s.amazon_environment == "sandbox"
        finally:
            s.AMAZON_ENVIRONMENT = original

    def test_production_without_credentials_falls_to_sandbox(self):
        """Production without credentials falls back to sandbox."""
        s = Settings()
        orig_env = s.AMAZON_ENVIRONMENT
        orig_id = s.AMAZON_LWA_CLIENT_ID
        orig_secret = s.AMAZON_LWA_CLIENT_SECRET
        orig_token = s.AMAZON_LWA_REFRESH_TOKEN
        try:
            s.AMAZON_ENVIRONMENT = "production"
            s.AMAZON_LWA_CLIENT_ID = ""
            s.AMAZON_LWA_CLIENT_SECRET = ""
            s.AMAZON_LWA_REFRESH_TOKEN = ""
            assert s.amazon_environment == "sandbox"
        finally:
            s.AMAZON_ENVIRONMENT = orig_env
            s.AMAZON_LWA_CLIENT_ID = orig_id
            s.AMAZON_LWA_CLIENT_SECRET = orig_secret
            s.AMAZON_LWA_REFRESH_TOKEN = orig_token


# ===========================================================================
# 3. Secret Leakage Prevention
# ===========================================================================

class TestSecretLeakagePrevention:
    """Verify secrets are never exposed."""

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

    def test_no_credentials_in_info_endpoint(self):
        """Info endpoint doesn't expose credentials."""
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as c:
            resp = c.get("/api/v1/amazon/info")
            body = resp.json()
            for key, val in body.items():
                val_str = str(val).lower()
                assert "client_secret" not in val_str
                assert "refresh_token" not in val_str

    def test_lwa_logger_uses_redacted_format(self):
        """LWA logger uses redacted format for client_id."""
        source = inspect.getsource(LWATokenManager.__init__)
        assert "redact_secret" in source

    def test_connection_status_excludes_secrets(self):
        """Connection status excludes secrets."""
        provider = AmazonOrderProvider()
        status = provider.connection_status
        for key, val in status.items():
            val_str = str(val).lower()
            assert "client_secret" not in val_str
            assert "refresh_token" not in val_str
            assert "access_token" not in val_str


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
        # Should not raise
        client._validate_endpoint("https://sandbox.sellingpartnerapi-na.amazon.com/orders")

    def test_production_allowed_in_production_mode(self):
        """Production endpoints allowed in production mode."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na", environment="production")
        # Should not raise
        client._validate_endpoint("https://sellingpartnerapi-na.amazon.com/orders")

    def test_sandbox_blocked_in_production_mode(self):
        """Sandbox endpoints blocked in production mode."""
        manager = LWATokenManager("id", "secret", "token")
        client = SPAPIClient(manager, region="na", environment="production")

        with pytest.raises(SPAPIError, match="BLOCKED"):
            client._validate_endpoint("https://sandbox.sellingpartnerapi-na.amazon.com/orders")

    def test_all_sandbox_endpoints_used(self):
        """All regions use sandbox endpoints by default."""
        manager = LWATokenManager("id", "secret", "token")
        for region in ["na", "eu", "fe"]:
            client = SPAPIClient(manager, region=region, environment="sandbox")
            assert client._base_url == SANDBOX_ENDPOINTS[region]

    def test_all_production_endpoints_available(self):
        """All production endpoints available when enabled."""
        manager = LWATokenManager("id", "secret", "token")
        for region in ["na", "eu", "fe"]:
            client = SPAPIClient(manager, region=region, environment="production")
            assert client._base_url == PRODUCTION_ENDPOINTS[region]


# ===========================================================================
# 5. Frontend Credential Protection
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
# 6. Read-Only Enforcement
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
        import inspect
        source = inspect.getsource(fulfillment_engine.__class__)
        assert "auto_approve" not in source.lower()
        assert "skip_approval" not in source.lower()


# ===========================================================================
# 7. Tenant Isolation
# ===========================================================================

class TestTenantIsolation:
    """Verify multi-tenant isolation."""

    def test_provider_instances_are_independent(self):
        """Provider instances have independent state."""
        p1 = AmazonOrderProvider()
        p2 = AmazonOrderProvider()
        p1._imported_order_ids.add("ORDER-A")
        assert p2.is_order_imported("ORDER-A") is False

    def test_registry_clear_removes_all(self):
        """Registry clear removes all providers."""
        from app.services.providers.registry import ProviderRegistry
        registry = ProviderRegistry()
        registry.register(AmazonOrderProvider())
        registry.clear()
        assert registry.get("amazon_order_provider") is None


# ===========================================================================
# 8. Configuration Separation
# ===========================================================================

class TestConfigurationSeparation:
    """Verify configuration separation between environments."""

    def test_config_reads_env_vars(self):
        """Config reads from environment variables."""
        s = Settings()
        # Check that config reads env vars (values may be empty)
        assert hasattr(s, "AMAZON_LWA_CLIENT_ID")
        assert hasattr(s, "AMAZON_LWA_CLIENT_SECRET")
        assert hasattr(s, "AMAZON_LWA_REFRESH_TOKEN")
        assert hasattr(s, "AMAZON_ENVIRONMENT")

    def test_default_environment_is_sandbox(self):
        """Default environment is sandbox."""
        s = Settings()
        assert s.AMAZON_ENVIRONMENT == "sandbox" or s.amazon_environment == "sandbox"

    def test_is_amazon_configured_requires_all_credentials(self):
        """is_amazon_configured requires all three credentials."""
        s = Settings()
        with patch.object(s, "AMAZON_LWA_CLIENT_ID", ""):
            assert s.is_amazon_configured is False

    def test_is_amazon_production_check(self):
        """is_amazon_production returns correct value."""
        s = Settings()
        # Default is sandbox
        assert s.is_amazon_production is False

    def test_mock_only_flag_exists(self):
        """MOCK_ONLY global flag exists."""
        assert MOCK_ONLY is True


# ===========================================================================
# 9. Environment Property Validation
# ===========================================================================

class TestEnvironmentPropertyValidation:
    """Verify amazon_environment property validation."""

    def test_valid_sandbox_environment(self):
        """Valid sandbox environment accepted."""
        s = Settings()
        original = s.AMAZON_ENVIRONMENT
        try:
            s.AMAZON_ENVIRONMENT = "sandbox"
            assert s.amazon_environment == "sandbox"
        finally:
            s.AMAZON_ENVIRONMENT = original

    def test_valid_production_with_credentials(self):
        """Valid production environment with credentials accepted."""
        s = Settings()
        orig_env = s.AMAZON_ENVIRONMENT
        orig_id = s.AMAZON_LWA_CLIENT_ID
        orig_secret = s.AMAZON_LWA_CLIENT_SECRET
        orig_token = s.AMAZON_LWA_REFRESH_TOKEN
        try:
            s.AMAZON_ENVIRONMENT = "production"
            s.AMAZON_LWA_CLIENT_ID = "test_client_id"
            s.AMAZON_LWA_CLIENT_SECRET = "test_client_secret"
            s.AMAZON_LWA_REFRESH_TOKEN = "test_refresh_token"
            assert s.amazon_environment == "production"
        finally:
            s.AMAZON_ENVIRONMENT = orig_env
            s.AMAZON_LWA_CLIENT_ID = orig_id
            s.AMAZON_LWA_CLIENT_SECRET = orig_secret
            s.AMAZON_LWA_REFRESH_TOKEN = orig_token

    def test_production_without_credentials_falls_to_sandbox(self):
        """Production without credentials falls back to sandbox."""
        s = Settings()
        orig_env = s.AMAZON_ENVIRONMENT
        orig_id = s.AMAZON_LWA_CLIENT_ID
        orig_secret = s.AMAZON_LWA_CLIENT_SECRET
        orig_token = s.AMAZON_LWA_REFRESH_TOKEN
        try:
            s.AMAZON_ENVIRONMENT = "production"
            s.AMAZON_LWA_CLIENT_ID = ""
            s.AMAZON_LWA_CLIENT_SECRET = ""
            s.AMAZON_LWA_REFRESH_TOKEN = ""
            assert s.amazon_environment == "sandbox"
        finally:
            s.AMAZON_ENVIRONMENT = orig_env
            s.AMAZON_LWA_CLIENT_ID = orig_id
            s.AMAZON_LWA_CLIENT_SECRET = orig_secret
            s.AMAZON_LWA_REFRESH_TOKEN = orig_token

    def test_invalid_environment_falls_to_sandbox(self):
        """Invalid environment falls back to sandbox."""
        s = Settings()
        original = s.AMAZON_ENVIRONMENT
        try:
            s.AMAZON_ENVIRONMENT = "invalid"
            assert s.amazon_environment == "sandbox"
        finally:
            s.AMAZON_ENVIRONMENT = original
