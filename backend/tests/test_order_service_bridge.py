"""Tests for order_service's temporary synchronous bridge (Phase 2B).

The bridge exists so services/fulfillment/workflow.py and
services/mock_amazon.py -- both synchronous, predating this migration -- can
reach the real PostgreSQL-backed async Order implementation. It runs a
single dedicated background event loop + its own AsyncEngine (NullPool),
independent of however many times an ASGI lifespan (e.g.
`with TestClient(app):`) starts and stops around it. See
app/services/order_service.py's module docstring for the full design
rationale (why a dedicated loop, why NullPool, why not the app's own loop).

These tests exercise the bridge directly (not through HTTP), and
specifically reproduce the failure mode the dedicated-loop design fixes:
"RuntimeError: Event loop is closed" from opening and closing multiple
independent TestClient/ASGI-lifespan cycles.
"""

import threading

import pytest
from fastapi.testclient import TestClient

from app.core.errors import NotFoundError
from app.main import app
from app.schemas.order import OrderCreate, OrderStatus
from app.services.order_service import order_service

from tests.conftest import create_test_organization


class TestBridgeSuccess:
    """A synchronous legacy caller reaches the real, PostgreSQL-backed
    async implementation and gets real data back."""

    def test_create_persists_and_returns_real_order(self):
        org_id = create_test_organization()
        order = order_service.create(
            OrderCreate(
                customer_name="Bridge Test Customer",
                shipping_address="1 Bridge St",
                product_name="Bridge Widget",
                quantity=1,
            ),
            org_id,
        )
        assert order.customer_name == "Bridge Test Customer"
        assert order.status == OrderStatus.PENDING

        fetched = order_service.get(order.id, org_id)
        assert fetched.id == order.id
        assert fetched.customer_name == "Bridge Test Customer"

    def test_update_status_persists(self):
        org_id = create_test_organization()
        order = order_service.create(
            OrderCreate(
                customer_name="Bridge Test",
                shipping_address="1 Bridge St",
                product_name="Widget",
                quantity=1,
            ),
            org_id,
        )
        updated = order_service.update_status(order.id, OrderStatus.PROCESSING, org_id)
        assert updated.status == OrderStatus.PROCESSING

        fetched = order_service.get(order.id, org_id)
        assert fetched.status == OrderStatus.PROCESSING


class TestBridgeExceptionPropagation:
    """An exception raised inside the real async implementation propagates
    back to the synchronous caller, not swallowed or hung."""

    def test_get_missing_order_raises_not_found(self):
        import uuid
        with pytest.raises(NotFoundError):
            order_service.get(uuid.uuid4(), create_test_organization())

    def test_get_wrong_organization_raises_not_found(self):
        """A real order, looked up under a different real organization,
        raises the same NotFoundError as a nonexistent order -- no
        existence leakage even at the bridge layer."""
        org_a = create_test_organization()
        org_b = create_test_organization()
        order = order_service.create(
            OrderCreate(
                customer_name="Org A Order",
                shipping_address="1 A St",
                product_name="Widget",
                quantity=1,
            ),
            org_a,
        )
        with pytest.raises(NotFoundError):
            order_service.get(order.id, org_b)


class TestClosedTestClientLoop:
    """Opening and closing a TestClient/ASGI lifespan must not poison the
    bridge for later use -- this is the exact scenario that produced
    'RuntimeError: Event loop is closed' before the dedicated-loop bridge
    redesign (see order_service.py's module docstring)."""

    def test_bridge_survives_testclient_close(self):
        with TestClient(app):
            pass  # lifespan starts and fully stops here

        # No TestClient/lifespan active at all right now -- the bridge must
        # still work, because it owns its own independent loop/thread.
        org_id = create_test_organization()
        order = order_service.create(
            OrderCreate(
                customer_name="After Close",
                shipping_address="1 St",
                product_name="Widget",
                quantity=1,
            ),
            org_id,
        )
        assert order.customer_name == "After Close"

    def test_bridge_survives_many_independent_lifespans(self):
        """Reproduces the exact original failure: several test files each
        open their own `with TestClient(app) as c:` block. Each one starts
        and stops a fresh ASGI lifespan (and, pre-fix, a fresh event loop
        the bridge would wrongly adopt and then lose)."""
        for _ in range(5):
            with TestClient(app):
                pass

        org_id = create_test_organization()
        order = order_service.create(
            OrderCreate(
                customer_name="Survived Many Lifespans",
                shipping_address="1 St",
                product_name="Widget",
                quantity=1,
            ),
            org_id,
        )
        fetched = order_service.get(order.id, org_id)
        assert fetched.customer_name == "Survived Many Lifespans"


class TestBridgeCleanup:
    """The bridge must not leak a new thread/loop per call -- exactly one
    dedicated bridge thread for the whole process, regardless of how many
    times it's used or how many ASGI lifespans start/stop around it."""

    def _bridge_thread_count(self) -> int:
        return sum(
            1 for t in threading.enumerate() if t.name == "order-service-bridge-loop"
        )

    def test_exactly_one_bridge_thread_after_many_calls(self):
        org_id = create_test_organization()
        for i in range(10):
            order_service.create(
                OrderCreate(
                    customer_name=f"Cleanup Test {i}",
                    shipping_address="1 St",
                    product_name="Widget",
                    quantity=1,
                ),
                org_id,
            )

        with TestClient(app):
            pass
        with TestClient(app):
            pass

        assert self._bridge_thread_count() == 1
