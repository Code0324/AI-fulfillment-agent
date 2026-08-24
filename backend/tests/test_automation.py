"""Tests for the automation sandbox endpoints.

Covers session management, form filling, approval workflow,
audit logging, security checks, and regression.
"""

import uuid

import pytest

from app.services.automation.engine import automation_engine


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_automation():
    """Clear automation state before every test."""
    automation_engine.clear()
    yield
    automation_engine.clear()


TEST_ADDRESS = {
    "first_name": "Test",
    "last_name": "Customer",
    "address_line_1": "123 Test Street",
    "address_line_2": "Apt 4",
    "city": "Testville",
    "state": "CA",
    "postal_code": "90210",
    "country": "US",
    "phone": "555-0123",
}


# ===========================================================================
# Session management
# ===========================================================================

class TestSessionManagement:
    """Automation session lifecycle."""

    def test_create_sandbox_session(self, client):
        resp = client.post("/api/v1/automation/sessions?environment=sandbox")
        assert resp.status_code == 201
        body = resp.json()
        assert body["environment"] == "sandbox"
        assert body["status"] == "idle"
        assert "id" in body

    def test_create_production_session_rejected(self, client):
        resp = client.post("/api/v1/automation/sessions?environment=production")
        assert resp.status_code == 422

    def test_get_session(self, client):
        created = client.post("/api/v1/automation/sessions?environment=sandbox").json()
        resp = client.get(f"/api/v1/automation/sessions/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_missing_session_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/automation/sessions/{fake_id}")
        assert resp.status_code == 404

    def test_list_sessions(self, client):
        client.post("/api/v1/automation/sessions?environment=sandbox")
        client.post("/api/v1/automation/sessions?environment=sandbox")
        resp = client.get("/api/v1/automation/sessions").json()
        assert resp["total_items"] == 2

    def test_stop_session(self, client):
        created = client.post("/api/v1/automation/sessions?environment=sandbox").json()
        resp = client.post(f"/api/v1/automation/sessions/{created['id']}/stop")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"


# ===========================================================================
# Form filling
# ===========================================================================

class TestFormFilling:
    """Form filling with normalized address data."""

    def test_fill_form_success(self, client):
        session = client.post("/api/v1/automation/sessions?environment=sandbox").json()
        payload = {
            "session_id": session["id"],
            "address": TEST_ADDRESS,
            "shipping_method": "express",
        }
        resp = client.post(f"/api/v1/automation/sessions/{session['id']}/fill", json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["filled_fields"]) > 0

    def test_fill_form_session_mismatch(self, client):
        session = client.post("/api/v1/automation/sessions?environment=sandbox").json()
        fake_id = str(uuid.uuid4())
        payload = {
            "session_id": fake_id,
            "address": TEST_ADDRESS,
        }
        resp = client.post(f"/api/v1/automation/sessions/{session['id']}/fill", json=payload)
        assert resp.status_code == 422

    def test_fill_form_missing_session(self, client):
        fake_id = str(uuid.uuid4())
        payload = {
            "session_id": fake_id,
            "address": TEST_ADDRESS,
        }
        resp = client.post(f"/api/v1/automation/sessions/{fake_id}/fill", json=payload)
        assert resp.status_code == 404


# ===========================================================================
# Approval workflow
# ===========================================================================

class TestApprovalWorkflow:
    """High-risk action approval system."""

    def test_safe_action_no_approval_needed(self, client):
        session = client.post("/api/v1/automation/sessions?environment=sandbox").json()
        resp = client.post(
            f"/api/v1/automation/sessions/{session['id']}/approve",
            params={"action": "fill", "description": "Fill form"},
        )
        assert resp.status_code == 422  # fill is safe, doesn't need approval

    def test_high_risk_action_requires_approval(self, client):
        session = client.post("/api/v1/automation/sessions?environment=sandbox").json()
        resp = client.post(
            f"/api/v1/automation/sessions/{session['id']}/approve",
            params={"action": "submit", "description": "Submit order"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending"
        assert body["action"] == "submit"

    def test_approve_request(self, client):
        session = client.post("/api/v1/automation/sessions?environment=sandbox").json()
        approval = client.post(
            f"/api/v1/automation/sessions/{session['id']}/approve",
            params={"action": "submit", "description": "Submit order"},
        ).json()
        resp = client.post(
            f"/api/v1/automation/approvals/{approval['id']}/respond",
            json={"status": "approved"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_reject_request(self, client):
        session = client.post("/api/v1/automation/sessions?environment=sandbox").json()
        approval = client.post(
            f"/api/v1/automation/sessions/{session['id']}/approve",
            params={"action": "submit", "description": "Submit order"},
        ).json()
        resp = client.post(
            f"/api/v1/automation/approvals/{approval['id']}/respond",
            json={"status": "rejected"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_double_respond_rejected(self, client):
        session = client.post("/api/v1/automation/sessions?environment=sandbox").json()
        approval = client.post(
            f"/api/v1/automation/sessions/{session['id']}/approve",
            params={"action": "submit", "description": "Submit order"},
        ).json()
        client.post(
            f"/api/v1/automation/approvals/{approval['id']}/respond",
            json={"status": "approved"},
        )
        resp = client.post(
            f"/api/v1/automation/approvals/{approval['id']}/respond",
            json={"status": "rejected"},
        )
        assert resp.status_code == 422

    def test_get_approval(self, client):
        session = client.post("/api/v1/automation/sessions?environment=sandbox").json()
        approval = client.post(
            f"/api/v1/automation/sessions/{session['id']}/approve",
            params={"action": "submit", "description": "Submit order"},
        ).json()
        resp = client.get(f"/api/v1/automation/approvals/{approval['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == approval["id"]


# ===========================================================================
# Sandbox page
# ===========================================================================

class TestSandboxPage:
    """Sandbox checkout page."""

    def test_sandbox_page_returns_html(self, client):
        resp = client.get("/api/v1/automation/sandbox")
        assert resp.status_code == 200
        assert "SANDBOX" in resp.text
        assert "NO AMAZON CONNECTION" in resp.text
        assert "first_name" in resp.text

    def test_sandbox_page_has_form_fields(self, client):
        resp = client.get("/api/v1/automation/sandbox")
        html = resp.text
        for field in ["first_name", "last_name", "address1", "city", "state", "zip", "shipping_method"]:
            assert field in html


# ===========================================================================
# Regression
# ===========================================================================

class TestRegressionExistingRoutes:
    """Ensure existing routes are unaffected."""

    def test_root_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_api_v1_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_api_v1_status(self, client):
        resp = client.get("/api/v1/status")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
