"""Tests for the generic Task API endpoints.

Covers POST, GET list (paginated), GET by ID, PATCH — plus 404,
validation errors, pagination edge cases, and regression checks.
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


def _create_task(client, status="pending"):
    """Helper: create a task and return the response JSON."""
    return client.post("/api/v1/tasks", json={"status": status}).json()


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
# GET /api/v1/tasks  (paginated)
# ===========================================================================

class TestListTasks:
    """GET /api/v1/tasks — paginated response."""

    # --- basic response shape ---

    def test_empty_list_returns_paginated_response(self, client):
        """Empty list returns valid paginated envelope with zero items."""
        resp = client.get("/api/v1/tasks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["page"] == 1
        assert body["page_size"] == 10
        assert body["total_items"] == 0
        assert body["total_pages"] == 0

    def test_returns_created_tasks_in_items(self, client):
        _create_task(client, "pending")
        _create_task(client, "running")
        resp = client.get("/api/v1/tasks")
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total_items"] == 2

    def test_list_preserves_insertion_order(self, client):
        r1 = _create_task(client, "running")
        r2 = _create_task(client, "completed")
        items = client.get("/api/v1/tasks").json()["items"]
        assert items[0]["id"] == r1["id"]
        assert items[1]["id"] == r2["id"]

    def test_response_is_paginated_type(self, client):
        resp = client.get("/api/v1/tasks")
        body = resp.json()
        assert isinstance(body["items"], list)
        assert isinstance(body["page"], int)
        assert isinstance(body["page_size"], int)
        assert isinstance(body["total_items"], int)
        assert isinstance(body["total_pages"], int)

    # --- pagination parameters ---

    def test_default_page_is_1(self, client):
        resp = client.get("/api/v1/tasks").json()
        assert resp["page"] == 1

    def test_default_page_size_is_10(self, client):
        resp = client.get("/api/v1/tasks").json()
        assert resp["page_size"] == 10

    def test_page_size_1_returns_single_item(self, client):
        for _ in range(5):
            _create_task(client)
        resp = client.get("/api/v1/tasks?page_size=1").json()
        assert len(resp["items"]) == 1
        assert resp["page_size"] == 1
        assert resp["total_items"] == 5
        assert resp["total_pages"] == 5

    def test_page_2_returns_second_slice(self, client):
        for _ in range(15):
            _create_task(client)
        resp = client.get("/api/v1/tasks?page=2&page_size=10").json()
        assert len(resp["items"]) == 5
        assert resp["page"] == 2

    def test_page_beyond_total_returns_empty_items(self, client):
        for _ in range(3):
            _create_task(client)
        resp = client.get("/api/v1/tasks?page=99&page_size=10").json()
        assert resp["items"] == []
        assert resp["total_items"] == 3

    def test_total_pages_calculation(self, client):
        """total_pages = ceil(total_items / page_size)."""
        for _ in range(25):
            _create_task(client)
        resp = client.get("/api/v1/tasks?page_size=10").json()
        assert resp["total_pages"] == 3

    def test_large_page_size_caps_at_100(self, client):
        """page_size > 100 is rejected with 422."""
        resp = client.get("/api/v1/tasks?page_size=101")
        assert resp.status_code == 422

    # --- validation ---

    def test_page_0_returns_422(self, client):
        resp = client.get("/api/v1/tasks?page=0")
        assert resp.status_code == 422

    def test_negative_page_returns_422(self, client):
        resp = client.get("/api/v1/tasks?page=-1")
        assert resp.status_code == 422

    def test_page_size_0_returns_422(self, client):
        resp = client.get("/api/v1/tasks?page_size=0")
        assert resp.status_code == 422

    def test_negative_page_size_returns_422(self, client):
        resp = client.get("/api/v1/tasks?page_size=-5")
        assert resp.status_code == 422

    def test_non_numeric_page_returns_422(self, client):
        resp = client.get("/api/v1/tasks?page=abc")
        assert resp.status_code == 422

    # --- edge cases ---

    def test_single_task_first_page(self, client):
        task = _create_task(client)
        resp = client.get("/api/v1/tasks?page=1&page_size=10").json()
        assert len(resp["items"]) == 1
        assert resp["items"][0]["id"] == task["id"]
        assert resp["total_items"] == 1
        assert resp["total_pages"] == 1

    def test_exact_page_boundary(self, client):
        """When total_items is an exact multiple of page_size, no extra page."""
        for _ in range(20):
            _create_task(client)
        resp = client.get("/api/v1/tasks?page_size=10").json()
        assert resp["total_pages"] == 2
        # page 3 should be empty
        resp3 = client.get("/api/v1/tasks?page=3&page_size=10").json()
        assert resp3["items"] == []


# ===========================================================================
# GET /api/v1/tasks/{task_id}
# ===========================================================================

class TestGetTask:
    """GET /api/v1/tasks/{task_id}"""

    def test_get_existing_task(self, client):
        created = _create_task(client)
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
        created = _create_task(client, "failed")
        resp = client.get(f"/api/v1/tasks/{created['id']}").json()
        assert set(resp.keys()) == {"id", "status", "created_at", "updated_at"}
        assert resp["status"] == "failed"


# ===========================================================================
# PATCH /api/v1/tasks/{task_id}
# ===========================================================================

class TestUpdateTask:
    """PATCH /api/v1/tasks/{task_id}"""

    def test_update_status_pending_to_running(self, client):
        created = _create_task(client)
        resp = client.patch(
            f"/api/v1/tasks/{created['id']}",
            json={"status": "running"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_update_status_running_to_completed(self, client):
        created = _create_task(client, "running")
        resp = client.patch(
            f"/api/v1/tasks/{created['id']}",
            json={"status": "completed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_update_status_to_failed(self, client):
        created = _create_task(client)
        resp = client.patch(
            f"/api/v1/tasks/{created['id']}",
            json={"status": "failed"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"

    def test_update_updates_timestamp(self, client):
        created = _create_task(client)
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
        created = _create_task(client)
        resp = client.patch(f"/api/v1/tasks/{created['id']}", json={})
        assert resp.status_code == 422

    @pytest.mark.parametrize("bad_status", ["unknown", "PENDING", "done", "cancelled"])
    def test_update_invalid_status_returns_422(self, client, bad_status):
        created = _create_task(client)
        resp = client.patch(
            f"/api/v1/tasks/{created['id']}",
            json={"status": bad_status},
        )
        assert resp.status_code == 422

    def test_update_validates_response_model(self, client):
        """Updated response fully validates against the Task schema."""
        from app.schemas.task import Task
        created = _create_task(client)
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
