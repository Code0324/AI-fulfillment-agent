"""Orchestrator (Multi-Client MCP) tests.

client_manager.py's routing/gating logic is tested here without spawning
real MCP server subprocesses (slow and environment-sensitive) — a minimal
fake ClientSession stands in for a real one, since MultiClientManager only
ever calls `.call_tool(name, arguments)` on it. permissions.py itself is
tested directly as pure functions.
"""

import asyncio
from types import SimpleNamespace

import pytest

from mcp_servers.orchestrator import permissions
from mcp_servers.orchestrator.client_manager import (
    ConfirmationRequiredError,
    MultiClientManager,
    ToolRoutingError,
)
from mcp_servers.orchestrator.config import load_server_configs


# ===========================================================================
# config.py
# ===========================================================================


def test_default_config_lists_all_four_servers():
    configs = load_server_configs()
    names = {c.name for c in configs}
    assert names == {"amazon", "tiktok_shop", "google_sheets", "notifications"}


def test_config_rejects_duplicate_server_names(tmp_path):
    bad_config = tmp_path / "dupes.json"
    bad_config.write_text(
        '{"servers": ['
        '{"name": "amazon", "command": "python"}, '
        '{"name": "amazon", "command": "python"}'
        "]}"
    )
    with pytest.raises(ValueError):
        load_server_configs(bad_config)


# ===========================================================================
# permissions.py
# ===========================================================================


class TestPermissions:
    @pytest.mark.parametrize(
        "tool_name",
        ["get_product", "check_price", "check_inventory", "get_order_status",
         "get_tracking", "get_orders", "get_order_details", "read_rows",
         "find_row"],
    )
    def test_read_tools_are_safe(self, tool_name):
        assert permissions.is_safe(tool_name) is True
        assert permissions.requires_confirmation(tool_name) is False

    @pytest.mark.parametrize(
        "tool_name",
        ["create_order", "update_fulfillment", "append_row", "update_row"],
    )
    def test_write_tools_require_confirmation(self, tool_name):
        assert permissions.is_safe(tool_name) is False
        assert permissions.requires_confirmation(tool_name) is True

    def test_unknown_tool_defaults_to_requiring_confirmation(self):
        """Safe-by-default: a tool that doesn't match a known safe prefix
        must not be freely callable just because it wasn't explicitly
        classified."""
        assert permissions.requires_confirmation("some_new_mystery_tool") is True

    def test_create_order_routes_through_fulfillment_approval(self):
        assert "create_order" in permissions.ROUTES_THROUGH_FULFILLMENT_APPROVAL


# ===========================================================================
# client_manager.py — routing + confirmation gate, with fake sessions
# ===========================================================================


class _FakeSession:
    """Stand-in for mcp.client.session.ClientSession — records the last
    call and returns a canned CallToolResult-shaped object."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="ok")], is_error=False)


def _manager_with_fake_servers() -> tuple[MultiClientManager, _FakeSession, _FakeSession]:
    """Build a MultiClientManager with its internal routing tables populated
    directly (bypassing connect_all's real subprocess spawning), mirroring
    exactly what _connect_one would have recorded for two servers that both
    expose a tool literally named "get_order_status" — the real collision
    between mcp_servers/amazon and mcp_servers/tiktok_shop."""
    manager = MultiClientManager(server_configs=[])
    amazon_session = _FakeSession()
    tiktok_session = _FakeSession()
    manager._sessions["amazon"] = amazon_session
    manager._sessions["tiktok_shop"] = tiktok_session

    for qualified, owner, original in [
        ("amazon__get_order_status", "amazon", "get_order_status"),
        ("amazon__create_order", "amazon", "create_order"),
        ("tiktok_shop__get_order_status", "tiktok_shop", "get_order_status"),
        ("tiktok_shop__update_fulfillment", "tiktok_shop", "update_fulfillment"),
    ]:
        manager._tool_owner[qualified] = owner
        manager._original_name[qualified] = original

    manager._connected = True
    return manager, amazon_session, tiktok_session


class TestMultiClientManagerRouting:
    def test_same_tool_name_on_two_servers_is_namespaced_not_collided(self):
        manager, _, _ = _manager_with_fake_servers()
        assert manager.owner_of("amazon__get_order_status") == "amazon"
        assert manager.owner_of("tiktok_shop__get_order_status") == "tiktok_shop"

    def test_call_routes_to_the_owning_server(self):
        manager, amazon_session, tiktok_session = _manager_with_fake_servers()

        asyncio.run(manager.call_tool("amazon__get_order_status", {"order_id": "1"}))
        assert amazon_session.calls == [("get_order_status", {"order_id": "1"})]
        assert tiktok_session.calls == []

        asyncio.run(manager.call_tool("tiktok_shop__get_order_status", {"order_id": "1"}))
        assert tiktok_session.calls == [("get_order_status", {"order_id": "1"})]

    def test_unknown_tool_raises_routing_error(self):
        manager, _, _ = _manager_with_fake_servers()
        with pytest.raises(ToolRoutingError):
            asyncio.run(manager.call_tool("nonexistent__tool", {}))

    def test_write_tool_without_confirmation_is_refused(self):
        """create_order (routes through the real fulfillment approval gate
        at the amazon server level) must never execute here without an
        explicit confirmed=True."""
        manager, amazon_session, _ = _manager_with_fake_servers()
        with pytest.raises(ConfirmationRequiredError):
            asyncio.run(manager.call_tool("amazon__create_order", {"sku": "x"}))
        assert amazon_session.calls == []  # never reached the underlying session

    def test_write_tool_with_confirmation_is_routed(self):
        manager, amazon_session, _ = _manager_with_fake_servers()
        asyncio.run(
            manager.call_tool("amazon__create_order", {"sku": "x"}, confirmed=True)
        )
        assert amazon_session.calls == [("create_order", {"sku": "x"})]

    def test_read_tool_never_needs_confirmation(self):
        manager, amazon_session, _ = _manager_with_fake_servers()
        asyncio.run(manager.call_tool("amazon__get_order_status", {"order_id": "1"}))
        assert amazon_session.calls  # succeeded without confirmed=True
