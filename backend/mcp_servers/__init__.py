"""MCP (Model Context Protocol) servers for the Amazon AI Fulfillment Agent.

These are real MCP servers (official Python SDK, package `mcp`) that sit
alongside the existing plain-Python provider architecture in
app/services/providers/ — they do not replace it. Every tool here is a thin
wrapper that calls into existing services (providers, the fulfillment
workflow engine, inventory/order services); no SP-API, TikTok Shop API, or
browser-automation logic is reimplemented here.

See mcp_servers/README.md for how to run each server and how the
orchestrator connects to them.
"""
