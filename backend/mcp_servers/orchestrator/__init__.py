"""Orchestrator (Multi-Client MCP) package.

An MCP *client* that connects to the amazon, tiktok_shop, and google_sheets
MCP servers, aggregates their tools, and re-exposes them as a single MCP
*server* (see server.py) — a gateway an AI agent can call without knowing
which underlying server owns which tool.
"""
