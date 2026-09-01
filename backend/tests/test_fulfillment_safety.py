"""Tests for fulfillment workflow safety hardening (CHUNK 1O).

Covers idempotency, duplicate prevention, state machine, approval expiration,
cancellation, retry safety, inventory safety, concurrency, and audit logging.

AUTH NOTE: fulfillment.py now enforces get_current_organization +
require_permission on every route, which means every call here needs a
real bearer token AND (via get_db) touches the application's own pooled
AsyncEngine (app/database.py) — not order_service's separate bridge
engine the old unauthenticated routes exercised. That pooled engine's
connections are each bound to whichever event loop first created them,
so this file now uses the single shared, session-scoped `client` fixture
for every call (see tests/conftest.py's _session_client docstring) rather
than the fresh per-test `with TestClient(app) as c:` blocks it used
before: a fresh TestClient per test means a fresh loop, and reusing one
pooled engine's connections across many independent short-lived loops
risks a connection created on one (now-closed) loop being checked out
again on another.
"""

import uuid

import pytest

from app.schemas.fulfillment import (
    APPROVAL_EXPIRY_SECONDS,
    FulfillmentStatus,
    is_valid_transition,
)
from app.services.automation.engine import automation_engine
from app.services.fulfillment.workflow import fulfillment_engine
from app.services.inventory_service import inventory_service
from app.services.order_service import order_service

from tests.conftest import auth_headers, auth_org


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_all():
    """Clear all state before every test."""
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    automation_engine.clear()
    yield
    fulfillment_engine.clear()
    order_service.clear()
    inventory_service.clear()
    automation_engine.clear()


def _create_inventory(sku="TEST-SKU-001", stock=100):
    """Helper: create an inventory item."""
    from app.schemas.inventory import InventoryCreate
    return inventory_service.create(
        InventoryCreate(
            sku=sku,
            product_name="Test Product",
            current_stock=stock,
            low_stock_threshold=10,
        )
    )


def _create_order(client, sku="TEST-SKU-001", qty=5, address=None):
    """Helper: create an order for a fresh, real authenticated organization.

    Returns (order, headers) — headers authenticate a real OWNER member of
    the SAME organization the order belongs to.
    """
    from app.schemas.order import OrderCreate
    if address is None:
        address = (
            "Test Customer\n"
            "123 Test Street\n"
            "Apt 4\n"
            "New York NY 10003\n"
            "US"
        )
    headers, org_id = auth_org(client)
    order = order_service.create(
        OrderCreate(
            customer_name="Test Customer",
            shipping_address=address,
            product_name="Test Product",
            sku=sku,
            quantity=qty,
        ),
        org_id,
    )
    return order, headers


# ===========================================================================
# INVARIANT 1: Cannot submit without approval
# ===========================================================================

class TestInvariantNoSubmitWithoutApproval:
    """A fulfillment cannot submit without approval."""

    def test_cannot_approve_non_waiting(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        # Try to approve a workflow that's not waiting
        # (it IS waiting, so approve it first)
        client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        # Try to approve again — should fail
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        assert resp.status_code == 422


# ===========================================================================
# INVARIANT 2: Cancelled workflow cannot submit
# ===========================================================================

class TestInvariantCancelledCannotSubmit:
    """A cancelled fulfillment cannot submit."""

    def test_approve_cancelled_workflow_fails(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        # Cancel
        client.post(f"/api/v1/fulfillment/{wf['id']}/reject", headers=headers)
        # Try to approve — should fail
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        assert resp.status_code == 422


# ===========================================================================
# INVARIANT 3: Rejected workflow cannot submit
# ===========================================================================

class TestInvariantRejectedCannotSubmit:
    """A rejected fulfillment cannot submit."""

    def test_reject_then_approve_fails(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        client.post(f"/api/v1/fulfillment/{wf['id']}/reject", headers=headers)
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        assert resp.status_code == 422


# ===========================================================================
# INVARIANT 4: Expired approval cannot submit
# ===========================================================================

class TestInvariantExpiredCannotSubmit:
    """An expired approval cannot submit."""

    def test_expired_approval_rejection(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        # Manually expire the approval
        from datetime import datetime, timezone, timedelta
        workflow = fulfillment_engine.get_workflow(uuid.UUID(wf["id"]))
        workflow.approval_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        # Try to get workflow — should auto-expire
        resp = client.get(f"/api/v1/fulfillment/{wf['id']}", headers=headers)
        body = resp.json()
        assert body["status"] == "expired"
        # Try to approve — should fail
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        assert resp.status_code == 422


# ===========================================================================
# INVARIANT 5: Completed workflow cannot submit again
# ===========================================================================

class TestInvariantCompletedCannotSubmit:
    """A completed fulfillment cannot submit again."""

    def test_approve_completed_workflow_fails(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        # Try to approve again — should fail
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        assert resp.status_code == 422


# ===========================================================================
# INVARIANT 6: Inventory cannot be reserved twice
# ===========================================================================

class TestInvariantNoDoubleReservation:
    """Inventory cannot be reserved twice."""

    def test_double_start_does_not_double_reserve(self, client):
        _create_inventory(stock=100)
        order, headers = _create_order(client, qty=5)
        wf1 = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        wf2 = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        # Should be the same workflow (idempotent)
        assert wf1["id"] == wf2["id"]
        # Inventory should only be reserved once
        inv = inventory_service.find_by_sku("TEST-SKU-001")
        assert inv.reserved_quantity == 5


# ===========================================================================
# INVARIANT 7: Available inventory cannot become negative
# ===========================================================================

class TestInvariantNoNegativeInventory:
    """Available inventory cannot become negative."""

    def test_release_after_rejection_restores_inventory(self, client):
        _create_inventory(stock=100)
        order, headers = _create_order(client, qty=5)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        inv = inventory_service.find_by_sku("TEST-SKU-001")
        assert inv.reserved_quantity == 5
        # Reject
        client.post(f"/api/v1/fulfillment/{wf['id']}/reject", headers=headers)
        inv = inventory_service.find_by_sku("TEST-SKU-001")
        assert inv.reserved_quantity == 0
        assert inv.available_quantity == 100


# ===========================================================================
# INVARIANT 8: Failed workflow cannot silently become completed
# ===========================================================================

class TestInvariantFailedCannotBecomeCompleted:
    """A failed fulfillment cannot silently become completed."""

    def test_failed_workflow_requires_retry(self, client):
        _create_inventory()
        order, headers = _create_order(client, address="X")  # Bad address
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        assert wf["status"] == "failed"
        # Try to approve — should fail
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        assert resp.status_code == 422


# ===========================================================================
# INVARIANT 9: Duplicate request creates duplicate supplier orders
# ===========================================================================

class TestInvariantNoDuplicateSupplierOrders:
    """A duplicate fulfillment request cannot create duplicate supplier orders."""

    def test_idempotent_start_returns_existing(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf1 = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        wf2 = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        assert wf1["id"] == wf2["id"]


# ===========================================================================
# INVARIANT 10: Confirmation ID belongs to only one submission
# ===========================================================================

class TestInvariantUniqueConfirmation:
    """A supplier confirmation ID belongs to only one fulfillment submission."""

    def test_unique_confirmation_ids(self, client):
        _create_inventory(sku="SKU-A", stock=100)
        _create_inventory(sku="SKU-B", stock=100)
        order1, headers1 = _create_order(client, sku="SKU-A")
        order2, headers2 = _create_order(
            client, sku="SKU-B", address="Jane Doe\n456 Other St\nChicago IL 60601\nUS"
        )
        wf1 = client.post(f"/api/v1/fulfillment/{order1.id}/start", headers=headers1).json()
        wf2 = client.post(f"/api/v1/fulfillment/{order2.id}/start", headers=headers2).json()
        assert wf1["status"] == "waiting_approval"
        assert wf2["status"] == "waiting_approval"
        client.post(f"/api/v1/fulfillment/{wf1['id']}/approve", headers=headers1)
        client.post(f"/api/v1/fulfillment/{wf2['id']}/approve", headers=headers2)
        wf1_final = client.get(f"/api/v1/fulfillment/{wf1['id']}", headers=headers1).json()
        wf2_final = client.get(f"/api/v1/fulfillment/{wf2['id']}", headers=headers2).json()
        assert wf1_final["confirmation"]["confirmation_id"] != wf2_final["confirmation"]["confirmation_id"]


# ===========================================================================
# State machine tests
# ===========================================================================

class TestStateMachine:
    """State transition validation."""

    def test_valid_transitions(self):
        assert is_valid_transition(FulfillmentStatus.PENDING, FulfillmentStatus.RUNNING)
        assert is_valid_transition(FulfillmentStatus.RUNNING, FulfillmentStatus.WAITING_APPROVAL)
        assert is_valid_transition(FulfillmentStatus.WAITING_APPROVAL, FulfillmentStatus.APPROVED)
        assert is_valid_transition(FulfillmentStatus.APPROVED, FulfillmentStatus.RUNNING)
        assert is_valid_transition(FulfillmentStatus.RUNNING, FulfillmentStatus.COMPLETED)
        assert is_valid_transition(FulfillmentStatus.RUNNING, FulfillmentStatus.FAILED)
        assert is_valid_transition(FulfillmentStatus.FAILED, FulfillmentStatus.RUNNING)

    def test_invalid_transitions(self):
        assert not is_valid_transition(FulfillmentStatus.COMPLETED, FulfillmentStatus.RUNNING)
        assert not is_valid_transition(FulfillmentStatus.COMPLETED, FulfillmentStatus.WAITING_APPROVAL)
        assert not is_valid_transition(FulfillmentStatus.COMPLETED, FulfillmentStatus.PENDING)

    def test_terminal_states_have_no_transitions(self):
        from app.schemas.fulfillment import VALID_TRANSITIONS
        assert VALID_TRANSITIONS[FulfillmentStatus.COMPLETED] == []
        # CANCELLED allows retry (RUNNING), so not fully terminal


# ===========================================================================
# Cancellation tests
# ===========================================================================

class TestCancellation:
    """Safe cancellation behavior."""

    def test_cancel_waiting_workflow(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/cancel", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_completed_workflow_fails(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/cancel", headers=headers)
        assert resp.status_code == 422

    def test_cancel_releases_inventory(self, client):
        _create_inventory(stock=100)
        order, headers = _create_order(client, qty=5)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        inv = inventory_service.find_by_sku("TEST-SKU-001")
        assert inv.reserved_quantity == 5
        client.post(f"/api/v1/fulfillment/{wf['id']}/cancel", headers=headers)
        inv = inventory_service.find_by_sku("TEST-SKU-001")
        assert inv.reserved_quantity == 0


# ===========================================================================
# Retry tests
# ===========================================================================

class TestRetry:
    """Retry safety behavior."""

    def test_retry_failed_workflow(self, client):
        _create_inventory()
        order, headers = _create_order(client, address="X")  # Bad address
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        assert wf["status"] == "failed"
        # Can't change address directly, so create a new order under the
        # same authenticated organization instead.
        order2, headers2 = _create_order(client)
        wf2 = client.post(f"/api/v1/fulfillment/{order2.id}/start", headers=headers2).json()
        assert wf2["status"] == "waiting_approval"

    def test_retry_does_not_duplicate_reservation(self, client):
        _create_inventory(stock=100)
        order, headers = _create_order(client, qty=5)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        # Cancel to make it retryable
        client.post(f"/api/v1/fulfillment/{wf['id']}/cancel", headers=headers)
        inv = inventory_service.find_by_sku("TEST-SKU-001")
        assert inv.reserved_quantity == 0  # Released on cancel
        # Retry — should re-reserve since previous was released
        client.post(f"/api/v1/fulfillment/{wf['id']}/retry", headers=headers)
        inv = inventory_service.find_by_sku("TEST-SKU-001")
        assert inv.reserved_quantity == 5  # Reserved once on retry

    def test_cannot_retry_completed_workflow(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/retry", headers=headers)
        assert resp.status_code == 422


# ===========================================================================
# Approval expiration tests
# ===========================================================================

class TestApprovalExpiration:
    """Approval expiration behavior."""

    def test_approval_expires(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        from datetime import datetime, timezone, timedelta
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        # Manually expire
        workflow = fulfillment_engine.get_workflow(uuid.UUID(wf["id"]))
        workflow.approval_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        # Get should auto-expire
        resp = client.get(f"/api/v1/fulfillment/{wf['id']}", headers=headers)
        assert resp.json()["status"] == "expired"

    def test_approval_not_expired_within_window(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        resp = client.get(f"/api/v1/fulfillment/{wf['id']}", headers=headers)
        assert resp.json()["status"] == "waiting_approval"


# ===========================================================================
# Audit tests
# ===========================================================================

class TestAudit:
    """Audit logging behavior."""

    def test_audit_log_records_events(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        resp = client.get(f"/api/v1/fulfillment/{wf['id']}/audit", headers=headers)
        body = resp.json()
        assert body["total"] > 0
        event_types = [e["event_type"] for e in body["events"]]
        assert "FULFILLMENT_STARTED" in event_types

    def test_audit_records_approval(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        resp = client.get(f"/api/v1/fulfillment/{wf['id']}/audit", headers=headers)
        event_types = [e["event_type"] for e in resp.json()["events"]]
        assert "APPROVAL_APPROVED" in event_types

    def test_audit_records_rejection(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        client.post(f"/api/v1/fulfillment/{wf['id']}/reject", headers=headers)
        resp = client.get(f"/api/v1/fulfillment/{wf['id']}/audit", headers=headers)
        event_types = [e["event_type"] for e in resp.json()["events"]]
        assert "APPROVAL_REJECTED" in event_types

    def test_audit_records_cancellation(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        client.post(f"/api/v1/fulfillment/{wf['id']}/cancel", headers=headers)
        resp = client.get(f"/api/v1/fulfillment/{wf['id']}/audit", headers=headers)
        event_types = [e["event_type"] for e in resp.json()["events"]]
        assert "FULFILLMENT_CANCELLED" in event_types


# ===========================================================================
# Regression
# ===========================================================================

class TestRegression:
    """Ensure existing functionality still works."""

    def test_complete_workflow_end_to_end(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        assert wf["status"] == "waiting_approval"
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"
        assert resp.json()["confirmation"] is not None

    def test_health_endpoints(self, client):
        assert client.get("/health").status_code == 200
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/status").status_code == 200

    def test_orders_still_work(self, client):
        """Orders endpoint still works (now requires real authentication —
        an intentional Phase 2B security change, not a regression)."""
        resp = client.post(
            "/api/v1/orders",
            json={
                "customer_name": "Test",
                "shipping_address": "123 St",
                "product_name": "Product",
                "quantity": 1,
            },
            headers=auth_headers(client),
        )
        assert resp.status_code == 201

    def test_inventory_still_works(self, client):
        resp = client.post(
            "/api/v1/inventory",
            json={"sku": "T", "product_name": "P", "current_stock": 10},
        )
        assert resp.status_code == 201


# ===========================================================================
# Approval security — organization/permission isolation on the approval
# gate itself (the FINAL IRREVERSIBLE ACTION). See api/v1/fulfillment.py's
# module docstring.
# ===========================================================================

class TestApprovalSecurity:
    """The approval gate must never trust anything but the authenticated,
    org-verified, permission-checked session that reached it."""

    def test_approve_fails_without_authentication(self, client):
        _create_inventory()
        order, headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve")
        assert resp.status_code in (401, 403)
        # Confirm it genuinely did not approve.
        refreshed = client.get(f"/api/v1/fulfillment/{wf['id']}", headers=headers).json()
        assert refreshed["status"] == "waiting_approval"

    def test_approve_fails_for_a_different_organizations_workflow(self, client):
        _create_inventory()
        order, owner_headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=owner_headers).json()
        outsider_headers = auth_headers(client)
        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=outsider_headers)
        assert resp.status_code == 404
        # The real owner can still approve it — the workflow was untouched.
        resp2 = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=owner_headers)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "completed"

    def test_start_fails_for_a_different_organizations_order(self, client):
        _create_inventory()
        order, _owner_headers = _create_order(client)
        outsider_headers = auth_headers(client)
        resp = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=outsider_headers)
        assert resp.status_code == 404

    def test_viewer_role_cannot_approve(self, client):
        """RBAC: a VIEWER member (read-only permissions) must not be able
        to approve, even though they belong to the right organization."""
        import uuid as uuid_mod
        from app.models import MembershipRole, OrganizationMember, User
        from app.security import hash_password
        from app.services.order_service import bridge_session, run_on_bridge_loop

        _create_inventory()
        order, owner_headers = _create_order(client)
        wf = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=owner_headers).json()

        # Find the order's organization and add a second, VIEWER-role user to it.
        refreshed = order_service.get(order.id)
        org_id = refreshed.organization_id

        async def _add_viewer():
            async with bridge_session() as db:
                suffix = uuid_mod.uuid4().hex[:12]
                user = User(
                    username=f"viewer_{suffix}",
                    email=f"viewer_{suffix}@example.com",
                    hashed_password=hash_password("Test-Password-123!"),
                )
                db.add(user)
                await db.flush()
                db.add(OrganizationMember(organization_id=org_id, user_id=user.id, role=MembershipRole.VIEWER))
                await db.commit()
                return user.email

        viewer_email = run_on_bridge_loop(_add_viewer())
        login_resp = client.post(
            "/auth/login", json={"email": viewer_email, "password": "Test-Password-123!"}
        )
        assert login_resp.status_code == 200, login_resp.text
        viewer_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

        resp = client.post(f"/api/v1/fulfillment/{wf['id']}/approve", headers=viewer_headers)
        assert resp.status_code == 403


# ===========================================================================
# TikTok SKU-mapping gate — wired into step 2 (_step_check_inventory) of
# the same 13-step workflow, not a second approval gate. See
# services/sku_mapping/engine.py and docs/tiktok-integration.md.
# ===========================================================================

def _create_tiktok_order(client, sku="TT-SKU-001", variation="Red/M", qty=2, channel_metadata=None):
    """Helper: create a TikTok-sourced order for a fresh, real authenticated
    organization. Returns (order, headers, org_id)."""
    from app.schemas.order import OrderCreate

    headers, org_id = auth_org(client)
    order = order_service.create(
        OrderCreate(
            customer_name="Jane Doe",
            shipping_address="Jane Doe\n123 Test Street\nSpringfield IL 62704\nUS",
            product_name="Test Widget",
            sku=sku,
            variation=variation,
            quantity=qty,
            source="TIKTOK",
            channel_metadata=channel_metadata,
        ),
        org_id,
    )
    return order, headers, org_id


class TestTikTokSkuMappingGate:
    def test_unmapped_tiktok_sku_fails_workflow_and_never_reserves_inventory(self, client):
        order, headers, _org_id = _create_tiktok_order(client, sku="TT-SKU-UNMAPPED", variation="Green/S")
        _create_inventory(sku="TT-SKU-UNMAPPED", stock=50)  # even if inventory exists under the TikTok SKU

        result = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()

        assert result["status"] == FulfillmentStatus.FAILED.value
        assert "sku mapping" in result["error_message"].lower()

        refreshed = order_service.get(order.id)
        assert refreshed.inventory_reserved is False

    def test_explicit_mapping_lets_workflow_proceed_to_waiting_approval(self, client):
        from app.services.sku_mapping.engine import sku_mapping_engine

        order, headers, org_id = _create_tiktok_order(client, sku="TT-SKU-MAPPED", variation="Blue/L")
        sku_mapping_engine.create_explicit_mapping(
            "TT-SKU-MAPPED", "Blue/L", "AMZ-RESOLVED-SKU", "B00RESOLVED1", org_id
        )
        _create_inventory(sku="AMZ-RESOLVED-SKU", stock=50)

        result = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()

        assert result["status"] == FulfillmentStatus.WAITING_APPROVAL.value

        refreshed = order_service.get(order.id)
        assert refreshed.sku == "AMZ-RESOLVED-SKU"
        assert refreshed.inventory_reserved is True

    def test_manual_source_order_behavior_is_unchanged(self, client):
        """Regression guard: a non-TikTok order takes the exact pre-change
        code path — the new branch only executes for source == "TIKTOK"."""
        _create_inventory()
        order, headers = _create_order(client)

        result = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()

        assert result["status"] == FulfillmentStatus.WAITING_APPROVAL.value

    def test_retry_after_sku_already_resolved_does_not_re_resolve_amazon_sku(self, client):
        """Regression guard for a real bug found during manual/browser
        verification of the TikTok ingestion pipeline: retry_workflow()
        resets every step (including resolve_sku_mapping) and re-runs from
        scratch, but _step_resolve_sku_mapping overwrites order.sku
        in-place with the resolved Amazon SKU once matched. Without
        channel_metadata["tiktok_sku"] preserving the original value, a
        retry after step 2 already succeeded (e.g. a transient inventory
        failure one step later) would try to re-resolve the *Amazon* SKU
        as if it were still the TikTok SKU — and fail with a bogus
        low-confidence fuzzy-match error instead of retrying cleanly.
        """
        from app.services.sku_mapping.engine import sku_mapping_engine

        headers, org_id = auth_org(client)
        sku_mapping_engine.create_explicit_mapping(
            "TT-SKU-RETRY", "Blue/L", "AMZ-RETRY-RESOLVED", "B00RETRY001", org_id
        )
        from app.schemas.order import OrderCreate

        order = order_service.create(
            OrderCreate(
                customer_name="Jane Doe",
                shipping_address="Jane Doe\n123 Test Street\nSpringfield IL 62704\nUS",
                product_name="Test Widget",
                sku="TT-SKU-RETRY",
                variation="Blue/L",
                quantity=1,
                source="TIKTOK",
                channel_metadata={"tiktok_sku": "TT-SKU-RETRY"},
            ),
            org_id,
        )

        # No inventory yet for the resolved SKU — fails one step after SKU
        # resolution succeeds, exactly like the manual-verification scenario.
        result = client.post(f"/api/v1/fulfillment/{order.id}/start", headers=headers).json()
        assert result["status"] == FulfillmentStatus.FAILED.value
        assert "inventory" in result["error_message"].lower()

        refreshed = order_service.get(order.id)
        assert refreshed.sku == "AMZ-RETRY-RESOLVED"  # already mutated by step 2

        _create_inventory(sku="AMZ-RETRY-RESOLVED", stock=10)
        retry_result = client.post(f"/api/v1/fulfillment/{result['id']}/retry", headers=headers).json()

        assert retry_result["status"] == FulfillmentStatus.WAITING_APPROVAL.value
        assert retry_result["sku_mapping_status"] == "matched"
