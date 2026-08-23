"""Tests for generic foundation schemas (common, status, task)."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.common import ApiResponse, PaginationMeta, StatusResponse
from app.schemas.status import AppStatus
from app.schemas.task import Task, TaskCreate, TaskStatus, TaskUpdate


# ---------------------------------------------------------------------------
# Common schemas
# ---------------------------------------------------------------------------
class TestCommonSchemas:
    def test_status_response_accepts_ok(self):
        model = StatusResponse(status="ok")
        assert model.status == "ok"

    def test_status_response_requires_status(self):
        with pytest.raises(ValidationError):
            StatusResponse()

    def test_pagination_meta_valid(self):
        meta = PaginationMeta(page=1, per_page=20, total_items=5, total_pages=1)
        assert meta.page == 1

    def test_pagination_meta_rejects_zero_page(self):
        with pytest.raises(ValidationError):
            PaginationMeta(page=0, per_page=20, total_items=0, total_pages=0)

    def test_api_response_defaults(self):
        model = ApiResponse(ok=True)
        assert model.ok is True
        assert model.data is None
        assert model.error is None
        assert model.meta is None

    def test_api_response_with_error(self):
        model = ApiResponse(ok=False, error="something failed")
        assert model.error == "something failed"


# ---------------------------------------------------------------------------
# Status schemas
# ---------------------------------------------------------------------------
class TestStatusSchemas:
    def test_app_status_minimal_body(self):
        model = AppStatus(status="ok")
        assert model.model_dump() == {"status": "ok"}

    def test_app_status_missing_status_rejected(self):
        with pytest.raises(ValidationError):
            AppStatus()


# ---------------------------------------------------------------------------
# Task schemas
# ---------------------------------------------------------------------------
class TestTaskSchemas:
    def test_task_create_defaults_to_pending(self):
        model = TaskCreate()
        assert model.status is TaskStatus.PENDING

    @pytest.mark.parametrize("status", ["pending", "running", "completed", "failed"])
    def test_task_create_accepts_all_statuses(self, status):
        model = TaskCreate(status=status)
        assert model.status == TaskStatus(status)

    @pytest.mark.parametrize("status", ["unknown", "PENDING", "", "done"])
    def test_task_create_rejects_invalid_status(self, status):
        with pytest.raises(ValidationError):
            TaskCreate(status=status)

    def test_task_update_accepts_none(self):
        model = TaskUpdate()
        assert model.status is None

    def test_task_update_accepts_valid_status(self):
        model = TaskUpdate(status="running")
        assert model.status is TaskStatus.RUNNING

    def test_task_update_rejects_invalid_status(self):
        with pytest.raises(ValidationError):
            TaskUpdate(status="cancelled")

    def test_task_round_trip(self):
        now = datetime.now(timezone.utc)
        task_id = uuid4()
        task = Task(
            id=task_id,
            status=TaskStatus.RUNNING,
            created_at=now,
            updated_at=now,
        )
        dumped = task.model_dump(mode="json")
        assert dumped["id"] == str(task_id)
        assert dumped["status"] == "running"
        restored = Task.model_validate(dumped)
        assert restored.id == task_id
        assert restored.status is TaskStatus.RUNNING

    def test_task_missing_required_fields_rejected(self):
        with pytest.raises(ValidationError):
            Task()
