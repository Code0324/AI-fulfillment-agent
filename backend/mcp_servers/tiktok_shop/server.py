"""TikTok Shop MCP server.

A TikTok provider already exists in this codebase at
app.services.providers.tiktok — TikTokOrderProvider — with exactly the four
methods this server needs to expose (get_orders, get_order_details,
get_order_status, update_fulfillment). This server wraps that provider; it
does not reimplement TikTok Shop API or signing logic.

Mock mode (TIKTOK_MOCK_MODE):
app.services.providers.tiktok.__init__ states, by explicit design, "There is
no MockTikTokProvider anywhere in this tree" — the real provider fails loudly
(ProviderUnavailableError) rather than silently returning empty/fake data
when not configured, specifically so a caller can never mistake "not
authorized" for "zero real orders". Adding a MockTikTokProvider under
app.services.providers.mock would contradict that deliberate decision.

So TIKTOK_MOCK_MODE is implemented at the MCP boundary only: when set, this
server returns clearly-labeled synthetic fixture data defined right here,
and never touches TikTokOrderProvider or real credentials. The provider
itself is completely unmodified. Default is real mode (TIKTOK_MOCK_MODE
unset/false) — this server calls the real provider and lets
ProviderUnavailableError surface as a normal tool error when TikTok Shop
credentials aren't configured, exactly like every other caller of
TikTokOrderProvider in this app.
"""

import logging
import os
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer

from app.services.providers.base import ProviderUnavailableError
from app.services.providers.tiktok.order_provider import TikTokOrderProvider

logger = logging.getLogger(__name__)

mcp = MCPServer("tiktok_shop")

_provider = TikTokOrderProvider()


def _mock_mode() -> bool:
    return os.getenv("TIKTOK_MOCK_MODE", "false").strip().lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# MCP-boundary-only synthetic fixtures — see module docstring for why these
# do not live in app.services.providers.mock.
# ---------------------------------------------------------------------------

_MOCK_TIKTOK_ORDERS: list[dict] = [
    {
        "tiktok_order_id": "TT-MOCK-000001",
        "source": "TIKTOK",
        "order_date": "2026-08-01T10:00:00+00:00",
        "sku": "TT-MOCK-SKU-001",
        "product_name": "Synthetic TikTok Widget Alpha",
        "variation": "Blue / M",
        "quantity": 2,
        "recipient_name": "Mock Recipient One",
        "phone_number": "555-0101",
        "address_line_1": "100 Mock Lane",
        "delivery_instructions": None,
        "city": "Seattle",
        "state": "WA",
        "zipcode": "98101",
        "price": 19.99,
        "delivery_date": None,
        "order_status": "AWAITING_SHIPMENT",
    },
    {
        "tiktok_order_id": "TT-MOCK-000002",
        "source": "TIKTOK",
        "order_date": "2026-08-02T11:30:00+00:00",
        "sku": "TT-MOCK-SKU-002",
        "product_name": "Synthetic TikTok Widget Beta",
        "variation": None,
        "quantity": 1,
        "recipient_name": "Mock Recipient Two",
        "phone_number": "555-0202",
        "address_line_1": "200 Test Drive",
        "delivery_instructions": "Leave at door",
        "city": "Portland",
        "state": "OR",
        "zipcode": "97201",
        "price": 34.50,
        "delivery_date": None,
        "order_status": "AWAITING_SHIPMENT",
    },
]


def _mock_order_by_id(order_id: str) -> dict | None:
    for order in _MOCK_TIKTOK_ORDERS:
        if order["tiktok_order_id"] == order_id:
            return order
    return None


@mcp.tool()
def get_orders() -> dict:
    """List TikTok Shop orders.

    In mock mode (TIKTOK_MOCK_MODE=true) returns synthetic fixture orders.
    Otherwise calls the real TikTokOrderProvider.get_orders(), which raises
    ProviderUnavailableError if TikTok Shop credentials aren't configured.
    """
    if _mock_mode():
        return {"mock": True, "orders": list(_MOCK_TIKTOK_ORDERS)}
    try:
        orders = _provider.get_orders()
    except ProviderUnavailableError as e:
        return {"mock": False, "error": str(e)}
    return {"mock": False, "orders": [o.model_dump(mode="json") for o in orders]}


@mcp.tool()
def get_order_details(order_id: str) -> dict:
    """Get full details for one TikTok Shop order.

    In mock mode, looks up the synthetic fixture set. Otherwise calls the
    real TikTokOrderProvider.get_order_details(), which raises
    ProviderUnavailableError if not configured.
    """
    if _mock_mode():
        order = _mock_order_by_id(order_id)
        if order is None:
            return {"mock": True, "order_id": order_id, "found": False}
        return {"mock": True, "order_id": order_id, "found": True, "order": order}
    try:
        order = _provider.get_order_details(order_id)
    except ProviderUnavailableError as e:
        return {"mock": False, "order_id": order_id, "error": str(e)}
    if order is None:
        return {"mock": False, "order_id": order_id, "found": False}
    return {"mock": False, "order_id": order_id, "found": True, "order": order.model_dump(mode="json")}


@mcp.tool()
def get_order_status(order_id: str) -> dict:
    """Get one TikTok Shop order's raw status string."""
    if _mock_mode():
        order = _mock_order_by_id(order_id)
        if order is None:
            return {"mock": True, "order_id": order_id, "found": False}
        return {"mock": True, "order_id": order_id, "found": True, "order_status": order["order_status"]}
    try:
        status = _provider.get_order_status(order_id)
    except ProviderUnavailableError as e:
        return {"mock": False, "order_id": order_id, "error": str(e)}
    if status is None:
        return {"mock": False, "order_id": order_id, "found": False}
    return {"mock": False, "order_id": order_id, "found": True, "order_status": status}


@mcp.tool()
def update_fulfillment(order_id: str, tracking_number: str, shipping_provider_id: str) -> dict:
    """Confirm shipment for a TikTok Shop order.

    This is a real write on TikTokOrderProvider (see that provider's
    docstring: gated purely by is_configured, not by this codebase's
    MOCK_ONLY flag — that flag guards the *supplier purchase* side, a
    separate concern). In mock mode this only updates the in-memory
    synthetic fixture and never touches the real provider/credentials.

    The orchestrator's permission layer (mcp_servers/orchestrator/
    permissions.py) flags this tool as requiring confirmation before an
    agent calls it unattended — see that module for details.
    """
    if _mock_mode():
        order = _mock_order_by_id(order_id)
        if order is None:
            return {"mock": True, "order_id": order_id, "found": False}
        order["order_status"] = "SHIPPED"
        return {
            "mock": True,
            "order_id": order_id,
            "found": True,
            "tracking_number": tracking_number,
            "shipping_provider_id": shipping_provider_id,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        }
    try:
        result = _provider.update_fulfillment(
            order_id, tracking_number=tracking_number, shipping_provider_id=shipping_provider_id
        )
    except ProviderUnavailableError as e:
        return {"mock": False, "order_id": order_id, "error": str(e)}
    return {"mock": False, "order_id": order_id, "result": result}


if __name__ == "__main__":
    mcp.run()
