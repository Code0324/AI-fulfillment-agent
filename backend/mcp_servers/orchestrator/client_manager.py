"""Multi-Client MCP manager.

Connects to every configured child MCP server (see config.py) over stdio,
aggregates their tool lists, and routes a tool call to the server that owns
it — so a caller doesn't need to know which server exposes which tool.
Applies the permissions.py confirmation gate before routing any call.

Tool names are namespaced as "{server_name}__{tool_name}" in the aggregated
list this manager exposes. Two of the child servers genuinely define a tool
with the same bare name (both amazon and tiktok_shop expose
get_order_status — see their respective server.py, per the task's tool
list for each) — bare-name aggregation would either collide or silently
shadow one of them, so every tool is namespaced by its owning server, not
just the colliding ones. permissions.py's safe/write classification still
operates on the *original* (un-namespaced) tool name, since that's what
carries the get_/check_/read_/... convention.
"""

import logging
from contextlib import AsyncExitStack

import mcp.types as types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from mcp_servers.orchestrator import permissions
from mcp_servers.orchestrator.config import ServerConfig, load_server_configs

logger = logging.getLogger(__name__)


class ToolRoutingError(Exception):
    """Raised when a tool name can't be routed to any connected server."""


class ConfirmationRequiredError(Exception):
    """Raised when a tool flagged by permissions.requires_confirmation is
    called without confirmed=True."""

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        note = (
            " It also routes through the fulfillment approval workflow — "
            "see mcp_servers/orchestrator/permissions.py."
            if tool_name in permissions.ROUTES_THROUGH_FULFILLMENT_APPROVAL
            else ""
        )
        super().__init__(
            f"Tool '{tool_name}' mutates state and requires confirmed=True.{note}"
        )


class MultiClientManager:
    """Connects to every configured MCP server and exposes one unified interface."""

    def __init__(self, server_configs: list[ServerConfig] | None = None) -> None:
        self._server_configs = server_configs
        self._stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        # Keyed by the namespaced "{server}__{tool}" name exposed to callers.
        self._tool_owner: dict[str, str] = {}
        self._tool_defs: dict[str, types.Tool] = {}
        self._original_name: dict[str, str] = {}
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect_all(self) -> None:
        """Connect to every configured server and discover its tools.

        Idempotent — a no-op once already connected.
        """
        if self._connected:
            return
        configs = self._server_configs or load_server_configs()
        for cfg in configs:
            await self._connect_one(cfg)
        self._connected = True

    async def _connect_one(self, cfg: ServerConfig) -> None:
        params = StdioServerParameters(
            command=cfg.command, args=cfg.args, cwd=cfg.cwd, env=cfg.env
        )
        try:
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
        except Exception as e:
            raise RuntimeError(f"Failed to connect to MCP server '{cfg.name}': {e}") from e

        self._sessions[cfg.name] = session
        tools = await session.list_tools()
        for tool in tools.tools:
            qualified_name = f"{cfg.name}__{tool.name}"
            if qualified_name in self._tool_owner:
                raise RuntimeError(f"Duplicate tool registration for '{qualified_name}'")
            self._tool_owner[qualified_name] = cfg.name
            self._original_name[qualified_name] = tool.name
            self._tool_defs[qualified_name] = tool.model_copy(update={"name": qualified_name})
        logger.info("Connected to MCP server '%s' — %d tool(s)", cfg.name, len(tools.tools))

    async def close(self) -> None:
        await self._stack.aclose()
        self._sessions.clear()
        self._tool_owner.clear()
        self._tool_defs.clear()
        self._original_name.clear()
        self._connected = False

    def list_tools(self) -> list[types.Tool]:
        """Aggregated tool list across every connected server, with each
        tool's name namespaced as "{server_name}__{tool_name}"."""
        return list(self._tool_defs.values())

    def owner_of(self, qualified_name: str) -> str | None:
        return self._tool_owner.get(qualified_name)

    async def call_tool(self, qualified_name: str, arguments: dict, *, confirmed: bool = False):
        """Route a tool call (by its namespaced "{server_name}__{tool_name}"
        name) to the server that owns it.

        Raises ToolRoutingError if no connected server owns this tool, or
        ConfirmationRequiredError if it mutates state and confirmed=False —
        see permissions.py for what "mutates state" means and why (checked
        against the tool's original, un-namespaced name).
        """
        server_name = self._tool_owner.get(qualified_name)
        if server_name is None:
            raise ToolRoutingError(f"No connected MCP server exposes tool '{qualified_name}'")

        original_name = self._original_name[qualified_name]
        if permissions.requires_confirmation(original_name) and not confirmed:
            raise ConfirmationRequiredError(original_name)

        session = self._sessions[server_name]
        return await session.call_tool(original_name, arguments)


# Module-level instance, used by orchestrator/server.py — mirrors this
# repo's existing convention of a single module-level singleton per service
# (provider_registry, fulfillment_engine, order_service, ...).
manager = MultiClientManager()
