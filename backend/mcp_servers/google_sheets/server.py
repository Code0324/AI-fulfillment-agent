"""Google Sheets MCP server.

PostgreSQL is the source of truth for this application. This server is a
REPORTING/OPERATIONS VIEW layer only — it lets an agent read/export/sync
spreadsheet rows for human visibility. Nothing in this server (or the
generic client it wraps, sheets_client.py) is ever fed back into this app's
own order/inventory/fulfillment state, and no MCP tool call here can
influence a fulfillment decision.
"""

import logging

from mcp.server.mcpserver import MCPServer

from mcp_servers.google_sheets.sheets_client import SheetsClientError, sheets_client

logger = logging.getLogger(__name__)

mcp = MCPServer("google_sheets")


@mcp.tool()
def read_rows(sheet_id: str, range: str) -> dict:
    """Read cell values for an A1 range (e.g. "Sheet1!A1:O50").

    Reporting/export only — read data is never treated as this app's source
    of truth (PostgreSQL is).
    """
    if not sheets_client.is_configured:
        return {"configured": False, "reason": "GOOGLE_SHEETS_CREDENTIALS_PATH is unset or invalid."}
    try:
        rows = sheets_client.read_rows(sheet_id, range)
    except SheetsClientError as e:
        return {"configured": True, "error": str(e)}
    return {"configured": True, "sheet_id": sheet_id, "range": range, "rows": rows}


@mcp.tool()
def append_row(sheet_id: str, values: list[str]) -> dict:
    """Append one row of values to the end of a sheet's default tab.

    Writes here are export/sync only — never read back as source of truth.
    """
    if not sheets_client.is_configured:
        return {"configured": False, "reason": "GOOGLE_SHEETS_CREDENTIALS_PATH is unset or invalid."}
    try:
        result = sheets_client.append_row(sheet_id, values)
    except SheetsClientError as e:
        return {"configured": True, "error": str(e)}
    return {"configured": True, "sheet_id": sheet_id, "result": result}


@mcp.tool()
def update_row(sheet_id: str, row_id: int, values: list[str]) -> dict:
    """Overwrite one 1-indexed row (starting at column A) with `values`.

    Writes here are export/sync only — never read back as source of truth.
    """
    if not sheets_client.is_configured:
        return {"configured": False, "reason": "GOOGLE_SHEETS_CREDENTIALS_PATH is unset or invalid."}
    try:
        result = sheets_client.update_row(sheet_id, row_id, values)
    except SheetsClientError as e:
        return {"configured": True, "error": str(e)}
    return {"configured": True, "sheet_id": sheet_id, "row_id": row_id, "result": result}


@mcp.tool()
def find_row(sheet_id: str, query: str) -> dict:
    """Find the first row (in the sheet's default tab) containing `query` in any cell."""
    if not sheets_client.is_configured:
        return {"configured": False, "reason": "GOOGLE_SHEETS_CREDENTIALS_PATH is unset or invalid."}
    try:
        match = sheets_client.find_row(sheet_id, query)
    except SheetsClientError as e:
        return {"configured": True, "error": str(e)}
    if match is None:
        return {"configured": True, "sheet_id": sheet_id, "query": query, "found": False}
    return {"configured": True, "sheet_id": sheet_id, "query": query, "found": True, **match}


@mcp.tool()
def fetch_pending_orders(sheet_id: str) -> dict:
    """Fetch all rows in the Orders tab where Status = Pending.

    Returns a list of order dicts with row_number, order_id, buyer_name,
    shipping fields, tiktok_sku, qty, price_paid, and status.
    """
    if not sheets_client.is_configured:
        return {"configured": False, "reason": "GOOGLE_SHEETS_CREDENTIALS_PATH is unset or invalid."}
    try:
        orders = sheets_client.fetch_pending_orders(sheet_id)
    except SheetsClientError as e:
        return {"configured": True, "error": str(e)}
    return {"configured": True, "sheet_id": sheet_id, "count": len(orders), "orders": orders}


@mcp.tool()
def update_order_status(
    sheet_id: str,
    row_number: int,
    status: str,
    amazon_asin_sku: str = "",
    amazon_order_id: str = "",
    tracking_number: str = "",
    notes: str = "",
) -> dict:
    """Update a specific order row's Status and Amazon-related fields.

    The row is identified by its 1-indexed row_number from fetch_pending_orders.
    """
    if not sheets_client.is_configured:
        return {"configured": False, "reason": "GOOGLE_SHEETS_CREDENTIALS_PATH is unset or invalid."}
    try:
        result = sheets_client.update_order_status(
            sheet_id, row_number, status,
            amazon_asin_sku=amazon_asin_sku,
            amazon_order_id=amazon_order_id,
            tracking_number=tracking_number,
            notes=notes,
        )
    except SheetsClientError as e:
        return {"configured": True, "error": str(e)}
    return {"configured": True, "sheet_id": sheet_id, "row_number": row_number, "result": result}


if __name__ == "__main__":
    mcp.run()
