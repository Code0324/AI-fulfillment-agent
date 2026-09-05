"""TikTok Shop MCP server tests.

No real TikTok Shop calls, no network requests, no real credentials — every
test either uses TIKTOK_MOCK_MODE (synthetic fixtures defined in
mcp_servers/tiktok_shop/server.py) or exercises the real, unconfigured
TikTokOrderProvider's documented fail-loud behavior.
"""

import asyncio

import pytest

from mcp_servers.tiktok_shop import server as tiktok_server


@pytest.fixture
def mock_mode(monkeypatch):
    monkeypatch.setenv("TIKTOK_MOCK_MODE", "true")


@pytest.fixture
def real_mode(monkeypatch):
    monkeypatch.delenv("TIKTOK_MOCK_MODE", raising=False)


def test_lists_expected_tools():
    tools = asyncio.run(tiktok_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {"get_orders", "get_order_details", "get_order_status", "update_fulfillment"}


# ===========================================================================
# Real mode — no credentials configured in this test environment. The
# provider's documented behavior (see app/services/providers/tiktok/
# order_provider.py) is to fail loudly, never return fabricated data.
# ===========================================================================


class TestRealModeWithoutCredentials:
    def test_get_orders_reports_error_not_empty_list(self, real_mode):
        result = tiktok_server.get_orders()
        assert result["mock"] is False
        assert "error" in result

    def test_get_order_details_reports_error(self, real_mode):
        result = tiktok_server.get_order_details("TT-1")
        assert result["mock"] is False
        assert "error" in result

    def test_update_fulfillment_reports_error_never_fabricates_confirmation(self, real_mode):
        result = tiktok_server.update_fulfillment("TT-1", "TRACK123", "usps")
        assert result["mock"] is False
        assert "error" in result


# ===========================================================================
# Mock mode — MCP-boundary-only synthetic fixtures. Never touches the real
# provider (see module docstring in mcp_servers/tiktok_shop/server.py for
# why this codebase deliberately has no MockTikTokProvider).
# ===========================================================================


class TestMockMode:
    def test_get_orders_returns_synthetic_fixtures(self, mock_mode):
        result = tiktok_server.get_orders()
        assert result["mock"] is True
        assert len(result["orders"]) > 0

    def test_get_order_details_returns_fixture_order(self, mock_mode):
        result = tiktok_server.get_order_details("TT-MOCK-000001")
        assert result["mock"] is True
        assert result["found"] is True
        assert result["order"]["tiktok_order_id"] == "TT-MOCK-000001"

    def test_get_order_details_unknown_id_reports_not_found(self, mock_mode):
        result = tiktok_server.get_order_details("TT-DOES-NOT-EXIST")
        assert result["found"] is False

    def test_update_fulfillment_updates_fixture_only(self, mock_mode):
        result = tiktok_server.update_fulfillment("TT-MOCK-000001", "TRACK-XYZ", "usps")
        assert result["mock"] is True
        assert result["tracking_number"] == "TRACK-XYZ"

        # Reflected in the fixture (mock mode is directly observable, unlike
        # a real write against TikTok's API).
        status = tiktok_server.get_order_status("TT-MOCK-000001")
        assert status["order_status"] == "SHIPPED"
