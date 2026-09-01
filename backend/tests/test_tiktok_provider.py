"""Tests for the TikTok Shop provider (CHUNK: TikTok provider + SKU mapping).

Every HTTP interaction in this file is mocked via unittest.mock.patch —
no real network access. Fixtures below are TEST FIXTURES only: they prove
this codebase's logic behaves correctly against a *given* response shape,
not that TikTok's real API actually returns that shape (see
docs/tiktok-integration.md's verification-status notes). There is no
MockTikTokProvider anywhere in this codebase — this file tests the real
provider's code paths with its network calls stubbed out.
"""

import inspect
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.providers.base import ProviderUnavailableError, ProviderValidationError
from app.services.providers.registry import provider_registry
from app.services.providers.tiktok.auth import (
    TikTokAuthenticationError,
    TikTokTokenManager,
    create_tiktok_token_manager_from_env,
    sign_request,
)
from app.services.providers.tiktok.api_client import TikTokAPIClient, TikTokAPIError
from app.services.providers.tiktok.order_provider import TikTokOrderProvider


# ---------------------------------------------------------------------------
# A realistic-shaped TikTok order fixture — a TEST FIXTURE, not proof a
# real TikTok API call returns this exact shape (field names here are the
# same UNVERIFIED best-guess names used in order_provider._normalize_order).
# ---------------------------------------------------------------------------

RAW_TIKTOK_ORDER_FIXTURE = {
    "id": "5771234567890123456",
    "create_time": 1735689600,
    "delivery_time": 1736294400,
    "status": "AWAITING_SHIPMENT",
    "recipient_address": {
        "name": "Jane Doe",
        "phone_number": "+15555550123",
        "address_line1": "123 Test Street",
        "delivery_instruction": "Leave at front door",
        "city": "Springfield",
        "state": "IL",
        "zipcode": "62704",
    },
    "line_items": [
        {
            "seller_sku": "TT-SKU-001",
            "sku_name": "Red/M",
            "product_name": "Test Widget",
            "quantity": "2",
            "sale_price": "19.99",
        }
    ],
}


def _token_manager(app_key="key", app_secret="secret", refresh_token="refresh") -> TikTokTokenManager:
    return TikTokTokenManager(app_key=app_key, app_secret=app_secret, refresh_token=refresh_token)


class TestOAuthConfigurationFailure:
    def test_factory_returns_none_without_env_vars(self, monkeypatch):
        for var in ("TIKTOK_APP_KEY", "TIKTOK_APP_SECRET", "TIKTOK_REFRESH_TOKEN", "TIKTOK_ACCESS_TOKEN"):
            monkeypatch.delenv(var, raising=False)
        assert create_tiktok_token_manager_from_env() is None

    def test_provider_not_configured_without_credentials(self):
        provider = TikTokOrderProvider(token_manager=None, shop_id=None, environment="sandbox")
        assert provider.is_configured is False

    def test_registry_does_not_register_unconfigured_provider(self):
        assert provider_registry.get_tiktok_provider() is None or provider_registry.get_tiktok_provider().is_configured

    def test_status_reports_not_configured_clearly(self):
        provider = TikTokOrderProvider(token_manager=None, shop_id=None, environment="sandbox")
        status = provider.connection_status
        assert status["configured"] is False
        assert "not configured" in status["notice"].lower()

    def test_public_methods_raise_rather_than_return_empty(self):
        provider = TikTokOrderProvider(token_manager=None, shop_id=None, environment="sandbox")
        with pytest.raises(ProviderUnavailableError):
            provider.get_orders()
        with pytest.raises(ProviderUnavailableError):
            provider.get_order_details("123")
        with pytest.raises(ProviderUnavailableError):
            provider.update_fulfillment("123", tracking_number="TRK1", shipping_provider_id="SP1")


class TestAuthenticationFailure:
    def test_invalid_client_response_raises(self):
        manager = _token_manager()
        response = httpx.Response(401, json={"code": "invalid_client", "message": "bad credentials"})
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=response)):
            with pytest.raises(TikTokAuthenticationError):
                import asyncio

                asyncio.run(manager.get_access_token())

    def test_missing_access_token_in_success_response_raises(self):
        manager = _token_manager()
        response = httpx.Response(200, json={"data": {}})
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=response)):
            with pytest.raises(TikTokAuthenticationError):
                import asyncio

                asyncio.run(manager.get_access_token())


class TestAPIErrors:
    def _client(self):
        manager = _token_manager()
        manager._access_token = "fake-token"
        import time

        manager._token_expires_at = time.time() + 3600
        return TikTokAPIClient(token_manager=manager, shop_id="shop123", environment="sandbox")

    def test_5xx_is_recoverable(self):
        client = self._client()
        response = httpx.Response(500, json={"message": "server error"})
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=response)):
            with pytest.raises(TikTokAPIError) as exc_info:
                import asyncio

                asyncio.run(client.search_orders())
        assert exc_info.value.recoverable is True

    def test_4xx_is_not_recoverable(self):
        client = self._client()
        response = httpx.Response(400, json={"message": "bad request"})
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=response)):
            with pytest.raises(TikTokAPIError) as exc_info:
                import asyncio

                asyncio.run(client.search_orders())
        assert exc_info.value.recoverable is False

    def test_business_error_envelope_on_http_200_is_still_an_error(self):
        client = self._client()
        response = httpx.Response(200, json={"code": 12345, "message": "shop not authorized"})
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=response)):
            with pytest.raises(TikTokAPIError):
                import asyncio

                asyncio.run(client.search_orders())


class TestPagination:
    def test_multi_page_search_is_followed(self):
        manager = _token_manager()
        manager._access_token = "fake-token"
        import time

        manager._token_expires_at = time.time() + 3600
        provider = TikTokOrderProvider(token_manager=manager, shop_id="shop123", environment="sandbox")

        page1 = httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "order_list": [RAW_TIKTOK_ORDER_FIXTURE],
                    "next_page_token": "page-2-token",
                },
            },
        )
        order2 = dict(RAW_TIKTOK_ORDER_FIXTURE)
        order2["id"] = "5771234567890123457"
        page2 = httpx.Response(
            200,
            json={"code": 0, "data": {"order_list": [order2], "next_page_token": None}},
        )

        with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=[page1, page2])):
            orders = provider.get_orders(limit=10)

        assert len(orders) == 2
        assert {o.tiktok_order_id for o in orders} == {
            "5771234567890123456",
            "5771234567890123457",
        }

    def test_stops_without_next_page_token(self):
        manager = _token_manager()
        manager._access_token = "fake-token"
        import time

        manager._token_expires_at = time.time() + 3600
        provider = TikTokOrderProvider(token_manager=manager, shop_id="shop123", environment="sandbox")

        single_page = httpx.Response(
            200,
            json={"code": 0, "data": {"order_list": [RAW_TIKTOK_ORDER_FIXTURE], "next_page_token": None}},
        )
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=single_page)):
            orders = provider.get_orders(limit=10)
        assert len(orders) == 1


class TestDuplicateOrdersIdempotency:
    """Exercises TikTokOrderProvider's dev/test-only in-memory import
    tracker, NOT the production DB-level idempotency constraint (see
    docs/tiktok-integration.md)."""

    def test_import_orders_twice_only_imports_once(self):
        manager = _token_manager()
        manager._access_token = "fake-token"
        import time

        manager._token_expires_at = time.time() + 3600
        provider = TikTokOrderProvider(token_manager=manager, shop_id="shop123", environment="sandbox")

        detail_response = httpx.Response(
            200, json={"code": 0, "data": {"order_list": [RAW_TIKTOK_ORDER_FIXTURE]}}
        )
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=detail_response)):
            first = provider.import_orders(["5771234567890123456"])
            second = provider.import_orders(["5771234567890123456"])

        assert first == ["5771234567890123456"]
        assert second == []
        assert provider.is_order_imported("5771234567890123456") is True


class TestNormalizedOrderData:
    def test_all_fifteen_business_fields_preserved(self):
        manager = _token_manager()
        provider = TikTokOrderProvider(token_manager=manager, shop_id="shop123", environment="sandbox")
        order = provider._normalize_order(RAW_TIKTOK_ORDER_FIXTURE)

        assert order.tiktok_order_id == "5771234567890123456"
        assert order.sku == "TT-SKU-001"
        assert order.product_name == "Test Widget"
        assert order.variation == "Red/M"
        assert order.quantity == 2
        assert order.recipient_name == "Jane Doe"
        assert order.phone_number == "+15555550123"
        assert order.address_line_1 == "123 Test Street"
        assert order.delivery_instructions == "Leave at front door"
        assert order.city == "Springfield"
        assert order.state == "IL"
        assert order.zipcode == "62704"
        assert order.price == 19.99
        assert order.delivery_date is not None
        assert order.order_status == "AWAITING_SHIPMENT"
        assert order.source == "TIKTOK"

    def test_malformed_order_raises_instead_of_guessing(self):
        manager = _token_manager()
        provider = TikTokOrderProvider(token_manager=manager, shop_id="shop123", environment="sandbox")
        with pytest.raises(ProviderValidationError):
            provider._normalize_order({"id": "123"})  # missing required nested data


class TestNoCredentialsAnywhere:
    def test_no_hardcoded_secrets_in_provider_source(self):
        source = inspect.getsource(TikTokOrderProvider)
        for forbidden in ("app_secret =", "client_secret =", "TIKTOK_APP_SECRET ="):
            assert forbidden not in source

    def test_no_hardcoded_secrets_in_auth_source(self):
        from app.services.providers.tiktok import auth as auth_module

        source = inspect.getsource(auth_module)
        assert "os.getenv" in source  # reads from env, doesn't hardcode
        assert "app_secret=\"" not in source


class TestSigningAndTokenRefresh:
    def test_signature_is_deterministic_for_known_inputs(self):
        sig1 = sign_request("/order/202309/orders/search", {"app_key": "abc", "timestamp": "1"}, "", "shh")
        sig2 = sign_request("/order/202309/orders/search", {"app_key": "abc", "timestamp": "1"}, "", "shh")
        assert sig1 == sig2
        assert len(sig1) == 64  # hex-encoded SHA-256

    def test_different_secret_changes_signature(self):
        sig1 = sign_request("/path", {"a": "1"}, "", "secret-one")
        sig2 = sign_request("/path", {"a": "1"}, "", "secret-two")
        assert sig1 != sig2

    def test_revoked_refresh_token_surfaces_authentication_error(self):
        manager = _token_manager()
        response = httpx.Response(401, json={"code": "invalid_grant", "message": "refresh token revoked"})
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=response)):
            with pytest.raises(TikTokAuthenticationError):
                import asyncio

                asyncio.run(manager.get_access_token())

    def test_token_refresh_happens_once_and_is_cached(self):
        manager = _token_manager()
        response = httpx.Response(
            200, json={"data": {"access_token": "new-token", "access_token_expire_in": 3600}}
        )
        mock_get = AsyncMock(return_value=response)
        with patch("httpx.AsyncClient.get", new=mock_get):
            import asyncio

            token1 = asyncio.run(manager.get_access_token())
            token2 = asyncio.run(manager.get_access_token())

        assert token1 == "new-token"
        assert token2 == "new-token"
        assert mock_get.call_count == 1  # second call served from cache
