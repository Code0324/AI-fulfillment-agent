"""Orchestrator MCP server — the "Multi-Client MCP".

Connects to the amazon, tiktok_shop, and google_sheets MCP servers (see
client_manager.py) and re-exposes their aggregated tools as a single MCP
server, so an AI agent can call any of them without knowing which
underlying server owns which tool.

Write tools (see permissions.py) require an extra "confirmed": true key in
the call arguments; without it, the call is refused with an explanation
instead of silently executing. This is a call-time safety prompt, not a
second approval queue — create_order's real approval gate remains the
existing fulfillment workflow (see mcp_servers/amazon/server.py and
permissions.py's module docstring).
"""

import asyncio
import logging

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from mcp_servers.orchestrator.client_manager import (
    ConfirmationRequiredError,
    ToolRoutingError,
    manager,
)

logger = logging.getLogger(__name__)


async def on_list_tools(ctx, params):
    if not manager.connected:
        await manager.connect_all()
    return types.ListToolsResult(tools=manager.list_tools())


async def on_call_tool(ctx, params):
    if not manager.connected:
        await manager.connect_all()

    arguments = dict(params.arguments or {})
    confirmed = bool(arguments.pop("confirmed", False))

    try:
        result = await manager.call_tool(params.name, arguments, confirmed=confirmed)
    except (ConfirmationRequiredError, ToolRoutingError) as e:
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=str(e))], isError=True
        )

    return types.CallToolResult(content=result.content, isError=result.is_error)


server = Server("orchestrator", on_list_tools=on_list_tools, on_call_tool=on_call_tool)


async def _run() -> None:
    await manager.connect_all()
    try:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(_run())
