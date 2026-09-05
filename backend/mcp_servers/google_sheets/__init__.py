"""Google Sheets MCP server package.

PostgreSQL is the source of truth for this application. This package is a
REPORTING/OPERATIONS VIEW layer only — export/sync to a spreadsheet for
human visibility — and must never be treated as authoritative order,
inventory, or fulfillment state.
"""
