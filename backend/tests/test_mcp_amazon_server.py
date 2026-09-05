"""Amazon MCP server tests.

Follows the pattern in test_provider_contract.py: exercises real service
singletons (order_service, fulfillment_engine, inventory_service) against
mock/synthetic data only, resetting state around every test. No real Amazon
calls, no network requests, no real credentials.
"""

import asyncio
import uuid

import pytest

from app.schemas.fulfillment import FulfillmentStatus
from app.schemas.inventory import InventoryCreate
from app.services.automation.engine import automation_engine
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.inventory_service import inventory_service
from app.services.order_service import order_service

from mcp_servers.amazon import server as amazon_server

from tests.conftest import create_test_organization


@pytest.fixture(autouse=True)
def _reset_all():
    """Clear all state before/after every test — same reset list as
    test_provider_contract.py's fixture."""
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    automation_engine.clear()
    yield
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    automation_engine.clear()


def _create_inventory(sku="MCP-AMZ-SKU-001", stock=100):
    return inventory_service.create(
        InventoryCreate(
            sku=sku,
            product_name="MCP Test Product",
            current_stock=stock,
            low_stock_threshold=10,
        )
    )


# ===========================================================================
# Tool listing
# ===========================================================================


def test_lists_expected_tools():
    """The server registers exactly the six required tools."""
    tools = asyncio.run(amazon_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "get_product",
        "check_price",
        "check_inventory",
        "get_order_status",
        "get_tracking",
        "create_order",
    }


# ===========================================================================
# Tools that report "not supported" rather than fabricating data
# ===========================================================================


def test_get_product_uses_active_pricing_provider():
    """Default PRICING_PROVIDER is mock — always configured, so this
    returns real (synthetic) product details rather than "not supported"."""
    result = amazon_server.get_product("B000TEST01")
    assert result["configured"] is True
    assert result["asin"] == "B000TEST01"
    assert "title" in result


def test_check_price_uses_active_pricing_provider():
    result = amazon_server.check_price("B000TEST01")
    assert result["configured"] is True
    assert isinstance(result["price"], float)


def test_get_order_status_reports_not_configured_without_credentials():
    result = amazon_server.get_order_status("TEST-ORDER")
    assert result["configured"] is False


def test_get_tracking_reports_not_configured_without_credentials():
    result = amazon_server.get_tracking("TEST-ORDER")
    assert result["configured"] is False


def test_check_inventory_internal_reports_not_found_without_sku_mapping():
    """No confirmed SKU mapping exists for this ASIN — must not fabricate
    one for the internal (our-warehouse) side of the result. The amazon
    (pricing-provider) side is independent and still real (mock)."""
    result = amazon_server.check_inventory("B0UNMAPPED0")
    assert result["internal"]["found"] is False
    assert result["amazon"]["configured"] is True


# ===========================================================================
# create_order routes through the existing approval gate — never executes
# a supplier submission directly.
# ===========================================================================


class TestCreateOrderApprovalGate:
    def test_create_order_returns_pending_approval_not_a_completed_order(self):
        """The tool never auto-approves — it must stop at WAITING_APPROVAL."""
        _create_inventory()
        org_id = create_test_organization()

        result = amazon_server.create_order(
            sku="MCP-AMZ-SKU-001",
            quantity=2,
            shipping_address="MCP Test Customer\n123 Test St\nNew York NY 10003\nUS",
            customer_name="MCP Test Customer",
            product_name="MCP Test Product",
            organization_id=str(org_id),
        )

        assert result["status"] == "pending_approval"
        assert result["order_id"]
        assert result["workflow_id"]

        # The underlying workflow really is sitting at WAITING_APPROVAL —
        # not just a status string the tool claims.
        workflow = fulfillment_engine.get_workflow(uuid.UUID(result["workflow_id"]))
        assert workflow.status == FulfillmentStatus.WAITING_APPROVAL

    def test_create_order_writes_asin_through_and_price_guard_uses_it(self):
        """The optional asin argument is written straight through to
        Order.asin (app/models.py) and used directly by the price
        safety-gate — top priority, no SKU-mapping needed."""
        _create_inventory()
        org_id = create_test_organization()

        result = amazon_server.create_order(
            sku="MCP-AMZ-SKU-001",
            quantity=1,
            shipping_address="MCP Test Customer\n123 Test St\nNew York NY 10003\nUS",
            customer_name="MCP Test Customer",
            product_name="MCP Test Product",
            organization_id=str(org_id),
            asin="B0MOCKASIN01",
        )

        assert result["status"] == "pending_approval"
        order = order_service.get(uuid.UUID(result["order_id"]))
        assert order.asin == "B0MOCKASIN01"

        workflow = fulfillment_engine.get_workflow(uuid.UUID(result["workflow_id"]))
        price_step = next(s for s in workflow.steps if s.name == "check_price_guard")
        assert "'asin_resolution': 'direct'" in price_step.result

    def test_create_order_without_asin_still_reaches_approval(self):
        """Omitting asin is safe — the price guard reports "not
        applicable" rather than blocking the order (safe default)."""
        _create_inventory()
        org_id = create_test_organization()

        result = amazon_server.create_order(
            sku="MCP-AMZ-SKU-001",
            quantity=1,
            shipping_address="MCP Test Customer\n123 Test St\nNew York NY 10003\nUS",
            customer_name="MCP Test Customer",
            product_name="MCP Test Product",
            organization_id=str(org_id),
        )

        assert result["status"] == "pending_approval"
        order = order_service.get(uuid.UUID(result["order_id"]))
        assert order.asin is None

    def test_create_order_does_not_reserve_inventory_beyond_the_normal_workflow_check(self):
        """No shortcut: the order still goes through the same inventory
        check every other order goes through (fails without inventory)."""
        org_id = create_test_organization()
        # No inventory created for this SKU.
        result = amazon_server.create_order(
            sku="MCP-NO-INVENTORY-SKU",
            quantity=1,
            shipping_address="MCP Test Customer\n123 Test St\nNew York NY 10003\nUS",
            customer_name="MCP Test Customer",
            product_name="MCP Test Product",
            organization_id=str(org_id),
        )
        assert result["status"] == "failed"

    def test_create_order_invalid_organization_id_is_rejected(self):
        """Never invents/defaults an organization — a bad id is a clean error."""
        result = amazon_server.create_order(
            sku="MCP-AMZ-SKU-001",
            quantity=1,
            shipping_address="addr",
            customer_name="Test",
            product_name="Widget",
            organization_id="not-a-uuid",
        )
        assert result["status"] == "error"

    def test_create_order_requires_explicit_approval_to_complete(self):
        """Only fulfillment_engine.approve_workflow — the existing approval
        queue — can move the order past pending_approval. Nothing in the
        MCP tool itself can do this."""
        _create_inventory()
        org_id = create_test_organization()

        result = amazon_server.create_order(
            sku="MCP-AMZ-SKU-001",
            quantity=1,
            shipping_address="MCP Test Customer\n123 Test St\nNew York NY 10003\nUS",
            customer_name="MCP Test Customer",
            product_name="MCP Test Product",
            organization_id=str(org_id),
        )
        workflow_id = uuid.UUID(result["workflow_id"])
        assert fulfillment_engine.get_workflow(workflow_id).status == FulfillmentStatus.WAITING_APPROVAL

        completed = fulfillment_engine.approve_workflow(workflow_id)
        assert completed.status == FulfillmentStatus.COMPLETED
