"""Tests for the generic Task API endpoints.

Covers POST, GET list, GET by ID, PATCH — plus 404, validation errors,
and regression checks for health/status routes.
"""

import uuid

import pytest

from app.services.task_service import task_service


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_task_service():
    """Clear in-memory store before every test so tests are independent."""
    task_service.clear()
    yield
    task_service.clear()


# ===========================================================================
# POST /api/v1/tasks
# ===========================================================================

class TestCreateTask:
    """POST /api/v1/tasks"""

    def test_create_default_status(self, client):
        """Task defaults to 'pending' when no body is sent."""
        resp = client.post("/api/v1/tasks")
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "pending"
        assert "id" in body
        assert "created_at" in body
        assert "updated_at" in body

    def test_create_explicit_pending(self, client):
        resp = client.post("/api/v1/tasks", json={"status": "pending"})
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    def test_create_explicit_running(self, client):
        resp = client.post("/api/v1/tasks", json={"status": "running"})
        assert resp.status_code == 201
        assert resp.json()["status"] == "running"

    def test_create_explicit_completed(self, client):
        resp = client.post("/api/v1/tasks", json={"status": "completed"})
        assert resp.status_code == 201
        assert resp.json()["status"] == "completed"

    def test_create_explicit_failed(self, client):
        resp = client.post("/api/v1/tasks", json={"status": "failed"})
        assert resp.status_code == 201
        assert resp.json()["status"] == "failed"

    @pytest.mark.parametrize("bad_status", ["unknown", "PENDING", "", "done", "cancelled"])
    def test_create_invalid_status_returns_422(self, client, bad_status):
        """Invalid status string is rejected by Pydantic validation."""
        resp = client.post("/api/v1/tasks", json={"status": bad_status})
        assert resp.status_code == 422

    def test_create_returns_unique_id(self, client):
        r1 = client.post("/api/v1/tasks").json()
        r2 = client.post("/api/v1/tasks").json()
        assert r1["id"] != r2["id"]

    def test_create_validates_response_model(self, client):
        """Response body fully validates against the Task schema."""
        from app.schemas.task import Task
        body = client.post("/api/v1/tasks").json()
        task = Task.model_validate(body)
        assert task.status.value == body["status"]


# ===========================================================================
# GET /api/v1/tasks
# ===========================================================================

class TestListTasks:
    """GET /api/v1/tasks"""

    def test_empty_list(self, client):
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_created_tasks(self, client):
        client.post("/api/v1/tasks", json={"status": "pending"})
        client.post("/api/v1/tasks", json={"status": "running"})
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) == 2

    def test_list_returns_insertion_order(self, client):
        r1 = client.post("/api/v1/tasks", json={"status": "running"})
        r2 = client.post("/api/v1/tasks", json={"status": "completed"})
        resp = client.get("/api/v1/tasks")
        items = resp.json()
        assert items[0]["id"] == r1.json()["id"]
        assert items[1]["id"] == r2.json()["id"]

    def test_list_returns_list_type(self, client):
        resp = client.get("/api/v1/tasks")
        assert isinstance(resp.json(), list)


# ===========================================================================
# GET /api/v1/tasks/{task_id}
# ===========================================================================

class TestGetTask:
    """GET /api/v1/tasks/{task_id}"""

    def test_get_existing_task(self, client):
        created = client.post("/api/v1/tasks").json()
        resp = client.get(f"/api/v1/tasks/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_missing_task_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/tasks/{fake_id}")
        assert resp.status_code == 404

    def test_get_404_body_has_error_key(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/tasks/{fake_id}")
        body = resp.json()
        assert "error" in body

    def test_get_returns_correct_fields(self, client):
        created = client.post("/api/v1/tasks", json={"status": "failed"}).json()
        resp = client.get(f"/api/v1/tasks/{created['id']}").json()
        assert set(resp.keys()) == {"id", "status", "created_at", "updated_at"}
        assert resp["status"] == "failed"


# ===========================================================================
# PATCH /api/v1/tasks/{task_id}
# ===========================================================================

class TestUpdateTask:
    """PATCH /api/v1/tasks/{task_id}"""

    def test_update_status_pending_to_running(self, client):
        created = client.post("/api/v1/tasks").json()
        resp = client.patch(
            f"/api/v1/tasks/{created['id']}",
            json={"status": "running"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_update_status_running_to_completed(self, client):
        created = client.post("/api/v1/tasks", json={"status": "running"}).json()
        resp = client.patch(
            f"/api/v1/tasks/{created['id']}",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_update_status_to_failed(self, client):
        created = client.post("/api/v1/tasks").json()
        resp = client.patch(
            f"/api/v1/tasks/{created['id']}",
            json={"status": "failed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

    def test_update_updates_timestamp(self, client):
        created = client.post("/api/v1/tasks").json()
        resp = client.patch(
            f"/api/v1/tasks/{created['id']}",
            json={"status": "running"},
        )
        assert resp.json()["updated_at"] >= created["updated_at"]

    def test_update_missing_task_returns_404(self, client):
        fake_id = str(uuid.uuid4())
        resp = client.patch(f"/api/v1/tasks/{fake_id}", json={"status": "running"})
        assert resp.status_code == 404

    def test_update_without_status_field_returns_422(self, client):
        """PATCH with empty body (no 'status') raises validation error."""
        created = client.post("/api/v1/tasks").json()
        resp = client.patch(f"/api/v1/tasks/{created['id']}", json={})
        assert resp.status_code == 422

    @pytest.mark.parametrize("bad_status", ["unknown", "PENDING", "done", "cancelled"])
    def test_update_invalid_status_returns_422(self, client, bad_status):
        created = client.post("/api/v1/tasks").json()
        resp = client.patch(
            f"/api/v1/tasks/{created['id']}",
            json={"status": bad_status},
        )
        assert resp.status_code == 422

    def test_update_validates_response_model(self, client):
        """Updated response fully validates against the Task schema."""
        from app.schemas.task import Task
        created = client.post("/api/v1/tasks").json()
        body = client.patch(
            f"/api/v1/tasks/{created['id']}",
            json={"status": "running"},
        ).json()
        task = Task.model_validate(body)
        assert task.status.value == "running"


# ===========================================================================
# Regression — existing routes still work
# ===========================================================================

class TestRegressionExistingRoutes:
    """Ensure health / status routes are unaffected by task routes."""

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
