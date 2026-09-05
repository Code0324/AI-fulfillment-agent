"""Fulfillment workflow price safety-gate tests (check_price_guard step).

Follows test_provider_contract.py's pattern: real service singletons
(order_service, fulfillment_engine, inventory_service, provider_registry),
mock/synthetic pricing data only, state reset around every test.

Hard safety rule under test: an order must NEVER reach WAITING_APPROVAL (or
any later state) if its Amazon price could not be verified or exceeds
MAX_ALLOWED_PRICE_USD — it must FAIL for human review instead. There is no
"skip the check" path.
"""

import pytest

from app.core.config import settings
from app.schemas.fulfillment import FulfillmentStatus, FulfillmentStepStatus
from app.schemas.inventory import InventoryCreate
from app.schemas.order import OrderCreate
from app.services.automation.engine import automation_engine
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.inventory_service import inventory_service
from app.services.order_service import order_service
from app.services.providers.amazon.pa_api_pricing import PAAPIPricingProvider
from app.services.providers.mock.mock_pricing import MockPricingProvider
from app.services.providers.registry import provider_registry
from app.services.sku_mapping.engine import sku_mapping_engine

from tests.conftest import create_test_organization


@pytest.fixture(autouse=True)
def _reset_all():
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    automation_engine.clear()
    provider_registry.set_pricing_provider(MockPricingProvider())
    yield
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    automation_engine.clear()
    provider_registry.set_pricing_provider(MockPricingProvider())


def _create_inventory(sku: str, stock: int = 100):
    return inventory_service.create(
        InventoryCreate(
            sku=sku,
            product_name="Price Gate Test Product",
            current_stock=stock,
            low_stock_threshold=10,
        )
    )


def _create_manual_order(org_id, sku: str, qty: int = 1):
    """A MANUAL order — no ASIN is ever resolvable for these."""
    return order_service.create(
        OrderCreate(
            customer_name="Price Gate Customer",
            shipping_address="Price Gate Customer\n123 Test St\nNew York NY 10003\nUS",
            product_name="Price Gate Test Product",
            sku=sku,
            quantity=qty,
            source="MANUAL",
        ),
        org_id,
    )


def _create_amazon_order_with_asin(org_id, asin: str, sku: str, qty: int = 1):
    """An Amazon-sourced order carrying a direct ASIN — see
    _step_check_price_guard's docstring: order.asin (a first-class column,
    app/models.py) is always priority 1 for ASIN resolution, regardless of
    source."""
    return order_service.create(
        OrderCreate(
            customer_name="Price Gate Customer",
            shipping_address="Price Gate Customer\n123 Test St\nNew York NY 10003\nUS",
            product_name="Price Gate Test Product",
            sku=sku,
            asin=asin,
            quantity=qty,
            source="MOCK_AMAZON",
        ),
        org_id,
    )


def _create_tiktok_order_with_confirmed_mapping(
    org_id, tiktok_sku: str, amazon_sku: str, mapped_asin: str, variation: str | None = None, qty: int = 1
):
    """A TIKTOK-sourced order with NO direct order.asin — its ASIN can only
    come from the SKU-mapping fallback (priority 2), via a real, explicitly
    confirmed mapping row (the only kind sku_mapping_engine.map_sku ever
    returns as MATCHED — see services/sku_mapping/engine.py)."""
    sku_mapping_engine.create_explicit_mapping(tiktok_sku, variation, amazon_sku, mapped_asin, org_id)
    return order_service.create(
        OrderCreate(
            customer_name="Price Gate Customer",
            shipping_address="Price Gate Customer\n123 Test St\nNew York NY 10003\nUS",
            product_name="Price Gate Test Product",
            sku=tiktok_sku,
            variation=variation,
            quantity=qty,
            source="TIKTOK",
        ),
        org_id,
    )


def _price_step(workflow):
    return next(s for s in workflow.steps if s.name == "check_price_guard")


# ===========================================================================
# No ASIN resolvable — not applicable, workflow proceeds normally
# ===========================================================================


class TestPriceGuardNotApplicable:
    def test_manual_order_has_no_asin_and_proceeds_to_approval(self):
        _create_inventory("PRICE-GATE-MANUAL")
        org_id = create_test_organization()
        order = _create_manual_order(org_id, "PRICE-GATE-MANUAL")

        wf = fulfillment_engine.start_workflow(order.id)

        assert wf.status == FulfillmentStatus.WAITING_APPROVAL
        assert _price_step(wf).status == FulfillmentStepStatus.COMPLETED

    def test_amazon_order_without_asin_field_proceeds_to_approval(self):
        """An Amazon-sourced order with order.asin unset (None) is "not
        applicable", same as MANUAL — never confused with "checked and
        fine", but also never blocks an order this codebase has no ASIN
        for. This is the exact safe-default behavior Gap A's task asked to
        preserve: no ASIN and no SKU-mapping match must still route
        safely (here: proceed, since there's nothing Amazon-priced to
        verify) rather than ever being treated as a block or as verified."""
        _create_inventory("PRICE-GATE-AMZ-NOASIN")
        org_id = create_test_organization()
        order = order_service.create(
            OrderCreate(
                customer_name="Price Gate Customer",
                shipping_address="Price Gate Customer\n123 Test St\nNew York NY 10003\nUS",
                product_name="Test Product",
                sku="PRICE-GATE-AMZ-NOASIN",
                quantity=1,
                source="MOCK_AMAZON",
            ),
            org_id,
        )
        assert order.asin is None
        wf = fulfillment_engine.start_workflow(order.id)
        assert wf.status == FulfillmentStatus.WAITING_APPROVAL
        price_step = _price_step(wf)
        assert "'applicable': False" in price_step.result


# ===========================================================================
# Direct order.asin field — priority 1, used regardless of source
# ===========================================================================


class TestPriceGuardDirectAsinResolution:
    def test_direct_asin_is_used_and_recorded_as_resolution_direct(self):
        _create_inventory("PRICE-GATE-DIRECT")
        org_id = create_test_organization()
        order = _create_amazon_order_with_asin(org_id, "B0MOCKASIN01", "PRICE-GATE-DIRECT")

        wf = fulfillment_engine.start_workflow(order.id)

        assert wf.status == FulfillmentStatus.WAITING_APPROVAL
        price_step = _price_step(wf)
        assert "'asin_resolution': 'direct'" in price_step.result
        assert "'asin': 'B0MOCKASIN01'" in price_step.result

    def test_direct_asin_takes_priority_over_sku_mapping_fallback(self):
        """A TIKTOK order with BOTH a direct order.asin AND a confirmed
        SKU-mapping resolving to a *different* (expensive, over-threshold)
        ASIN: only the direct one must be used. Proven by the workflow
        passing the price check at all — B0MOCKASIN03's mock price
        ($899.99) is over the default $500 threshold and would fail the
        workflow if the SKU-mapping's ASIN were used instead.
        """
        _create_inventory("PRICE-GATE-PRIORITY")
        org_id = create_test_organization()
        sku_mapping_engine.create_explicit_mapping(
            "TT-PRIORITY-SKU", None, "PRICE-GATE-PRIORITY", "B0MOCKASIN03", org_id
        )
        order = order_service.create(
            OrderCreate(
                customer_name="Price Gate Customer",
                shipping_address="Price Gate Customer\n123 Test St\nNew York NY 10003\nUS",
                product_name="Price Gate Test Product",
                sku="TT-PRIORITY-SKU",
                asin="B0MOCKASIN01",  # cheap ($19.99) — must win over the mapping's B0MOCKASIN03
                quantity=1,
                source="TIKTOK",
            ),
            org_id,
        )

        wf = fulfillment_engine.start_workflow(order.id)

        assert wf.status == FulfillmentStatus.WAITING_APPROVAL
        price_step = _price_step(wf)
        assert "'asin_resolution': 'direct'" in price_step.result
        assert "'asin': 'B0MOCKASIN01'" in price_step.result


# ===========================================================================
# SKU-mapping fallback (priority 2) — TikTok orders with no direct ASIN
# ===========================================================================


class TestPriceGuardSkuMappingFallback:
    def test_tiktok_order_with_confirmed_mapping_resolves_via_fallback(self):
        _create_inventory("PRICE-GATE-TT-MAPPED")
        org_id = create_test_organization()
        order = _create_tiktok_order_with_confirmed_mapping(
            org_id,
            tiktok_sku="TT-FALLBACK-SKU",
            amazon_sku="PRICE-GATE-TT-MAPPED",
            mapped_asin="B0MOCKASIN01",
        )

        wf = fulfillment_engine.start_workflow(order.id)

        assert wf.status == FulfillmentStatus.WAITING_APPROVAL
        price_step = _price_step(wf)
        assert "'asin_resolution': 'sku_mapping'" in price_step.result
        assert "'asin': 'B0MOCKASIN01'" in price_step.result

    def test_tiktok_order_mapping_over_threshold_still_stops(self, monkeypatch):
        """The fallback path is just as safety-gated as the direct path —
        confirms Gap A didn't accidentally weaken the pre-existing
        SKU-mapping resolution behavior."""
        _create_inventory("PRICE-GATE-TT-EXPENSIVE")
        org_id = create_test_organization()
        monkeypatch.setattr(settings, "MAX_ALLOWED_PRICE_USD", 10.0)
        order = _create_tiktok_order_with_confirmed_mapping(
            org_id,
            tiktok_sku="TT-EXPENSIVE-SKU",
            amazon_sku="PRICE-GATE-TT-EXPENSIVE",
            mapped_asin="B0MOCKASIN01",  # $19.99 > $10 threshold
        )

        wf = fulfillment_engine.start_workflow(order.id)

        assert wf.status == FulfillmentStatus.FAILED
        assert "exceeds the maximum allowed" in wf.error_message


# ===========================================================================
# Price exceeds threshold — hard STOP
# ===========================================================================


class TestPriceGuardStopsOnHighPrice:
    def test_price_over_threshold_fails_workflow_before_approval(self, monkeypatch):
        _create_inventory("PRICE-GATE-EXPENSIVE")
        org_id = create_test_organization()
        monkeypatch.setattr(settings, "MAX_ALLOWED_PRICE_USD", 10.0)
        # B0MOCKASIN01 -> mock price $19.99, well over the $10 threshold.
        order = _create_amazon_order_with_asin(org_id, "B0MOCKASIN01", "PRICE-GATE-EXPENSIVE")

        wf = fulfillment_engine.start_workflow(order.id)

        assert wf.status == FulfillmentStatus.FAILED
        assert "exceeds the maximum allowed" in wf.error_message
        assert _price_step(wf).status == FulfillmentStepStatus.FAILED
        # Must never reach the approval step at all.
        approval_step = next(s for s in wf.steps if s.name == "request_approval")
        assert approval_step.status == FulfillmentStepStatus.PENDING

    def test_price_over_threshold_never_reserves_inventory(self, monkeypatch):
        """The workflow must stop before any of the normal downstream side
        effects (inventory reservation) happen."""
        _create_inventory("PRICE-GATE-EXPENSIVE-2", stock=50)
        org_id = create_test_organization()
        monkeypatch.setattr(settings, "MAX_ALLOWED_PRICE_USD", 10.0)
        order = _create_amazon_order_with_asin(org_id, "B0MOCKASIN01", "PRICE-GATE-EXPENSIVE-2")

        fulfillment_engine.start_workflow(order.id)

        item = inventory_service.find_by_sku("PRICE-GATE-EXPENSIVE-2")
        assert item.reserved_quantity == 0


# ===========================================================================
# Pricing provider unavailable/errors — hard STOP, never skipped
# ===========================================================================


class TestPriceGuardStopsWhenProviderUnavailable:
    def test_unconfigured_provider_fails_workflow_never_auto_approves(self):
        _create_inventory("PRICE-GATE-NOPROVIDER")
        org_id = create_test_organization()
        provider_registry.set_pricing_provider(PAAPIPricingProvider(enabled=False))
        order = _create_amazon_order_with_asin(org_id, "B0ANY", "PRICE-GATE-NOPROVIDER")

        wf = fulfillment_engine.start_workflow(order.id)

        assert wf.status == FulfillmentStatus.FAILED
        assert "Routing to human review" in wf.error_message
        approval_step = next(s for s in wf.steps if s.name == "request_approval")
        assert approval_step.status == FulfillmentStepStatus.PENDING


# ===========================================================================
# Price within threshold — proceeds normally, still requires the existing
# separate human-approval gate before submission.
# ===========================================================================


class TestPriceGuardPassesWithinThreshold:
    def test_price_within_threshold_reaches_the_existing_approval_gate(self):
        _create_inventory("PRICE-GATE-OK")
        org_id = create_test_organization()
        # B0MOCKASIN01 -> $19.99, well under the default $500 threshold.
        order = _create_amazon_order_with_asin(org_id, "B0MOCKASIN01", "PRICE-GATE-OK")

        wf = fulfillment_engine.start_workflow(order.id)

        assert wf.status == FulfillmentStatus.WAITING_APPROVAL
        price_step = _price_step(wf)
        assert price_step.status == FulfillmentStepStatus.COMPLETED
        assert "'checked': True" in price_step.result
        assert "'applicable': True" in price_step.result

    def test_approving_afterward_still_requires_the_separate_approval_step(self):
        """The price guard is not itself an approval mechanism — completing
        it does not skip the existing human-approval gate."""
        _create_inventory("PRICE-GATE-OK-2")
        org_id = create_test_organization()
        order = _create_amazon_order_with_asin(org_id, "B0MOCKASIN01", "PRICE-GATE-OK-2")

        wf = fulfillment_engine.start_workflow(order.id)
        assert wf.status == FulfillmentStatus.WAITING_APPROVAL

        completed = fulfillment_engine.approve_workflow(wf.id)
        assert completed.status == FulfillmentStatus.COMPLETED
