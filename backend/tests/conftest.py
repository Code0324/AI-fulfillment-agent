"""Shared test fixtures."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import MembershipRole, Organization, OrganizationMember, User
from app.security import hash_password
from app.services.order_service import bridge_session, run_on_bridge_loop


@pytest.fixture(scope="session", autouse=True)
def _session_client():
    """One TestClient — and one continuously-running event loop — for the
    whole test session.

    order_service's synchronous bridge (see app/services/order_service.py)
    schedules work onto whatever loop app.main's lifespan captured, and
    needs that loop to still be alive whenever it's used. A fresh
    TestClient per test would give each test its own loop and close it at
    teardown; any autouse fixture that calls order_service directly without
    depending on `client` (e.g. test_fulfillment.py's _reset_all) could then
    run before any loop exists, or after the one it needs has already been
    closed by a previous test. Session-scoping this — and making it
    autouse, so it always runs first regardless of which fixtures a given
    test file requests — avoids both problems: there is exactly one loop,
    captured once, alive for the entire test run.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client(_session_client):
    """Provide the shared session TestClient, reset to an unauthenticated
    state for this test."""
    _session_client.headers.pop("Authorization", None)
    _session_client.cookies.clear()
    yield _session_client
    _session_client.headers.pop("Authorization", None)
    _session_client.cookies.clear()


def create_test_organization() -> uuid.UUID:
    """Create a real User + Organization (+ OWNER membership) directly in
    the database and return the organization's id.

    For test setup only. Used by test files that exercise services below
    the authenticated HTTP layer (test_fulfillment.py,
    test_fulfillment_safety.py, test_mock_amazon.py) and therefore need a
    real organization_id to satisfy FulfillmentOrder.organization_id's NOT
    NULL foreign key, without going through the /auth/signup +
    /organizations HTTP flow that test_orders.py exercises instead. This
    creates a genuine row in every relevant table — never a
    default/fabricated organization_id.

    Runs via order_service's dedicated bridge loop (run_on_bridge_loop /
    bridge_session), not a fresh asyncio.run() against the application's own
    pooled engine: a fresh event loop per asyncio.run() call, repeatedly
    sharing one pooled AsyncEngine (app/database.py's `engine`, whose pooled
    connections are each bound to whichever loop created them) across many
    such calls, hits the same cross-event-loop pooled-connection hazard the
    bridge redesign exists to avoid (asyncpg raises "Task ... attached to a
    different loop" / "no current event loop" once a connection opened on
    one now-closed asyncio.run() loop gets checked out again on another).
    The bridge loop is a single long-lived loop with its own NullPool
    engine, so this is safe to call many times across a test session.
    """

    async def _create() -> uuid.UUID:
        async with bridge_session() as db:
            suffix = uuid.uuid4().hex[:12]
            user = User(
                username=f"testuser_{suffix}",
                email=f"testuser_{suffix}@example.test",
                hashed_password=hash_password("Test-Password-123!"),
            )
            db.add(user)
            await db.flush()
            org = Organization(name=f"Test Org {suffix}", slug=f"test-org-{suffix}")
            db.add(org)
            await db.flush()
            db.add(
                OrganizationMember(
                    organization_id=org.id, user_id=user.id, role=MembershipRole.OWNER
                )
            )
            await db.commit()
            return org.id

    return run_on_bridge_loop(_create())


def auth_headers(http_client) -> dict[str, str]:
    """Sign up a fresh real user and real organization through the actual
    HTTP authentication flow (/auth/signup + /organizations — the same
    endpoints a real customer uses) and return an Authorization header
    carrying a real JWT for that user/org.

    For HTTP-level test setup only (test_orders.py and the various
    "existing routes still work" regression checks scattered across other
    test files). Every order endpoint is authenticated as of Phase 2B, so
    any test hitting /api/v1/orders over HTTP needs a real bearer token —
    there is no default/fallback organization to fall back to.
    """
    suffix = uuid.uuid4().hex[:12]
    resp = http_client.post(
        "/auth/signup",
        json={
            "email": f"testuser_{suffix}@example.com",
            "username": f"testuser_{suffix}",
            "password": "Test-Password-123!",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = http_client.post(
        "/organizations",
        json={"name": f"Test Org {suffix}", "slug": f"test-org-{suffix}"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    return headers
