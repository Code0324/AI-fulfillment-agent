"""API v1 task routes — generic in-memory task foundation."""

from uuid import UUID

from fastapi import APIRouter, status as http_status

from app.core.errors import ValidationError
from app.schemas.task import Task, TaskCreate, TaskUpdate
from app.services.task_service import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=Task, status_code=http_status.HTTP_201_CREATED)
def create_task(payload: TaskCreate | None = None) -> Task:
    """Create a new generic task.

    Accepts an optional body — defaults to ``TaskCreate()``
    (status=pending) when omitted.
    """
    return task_service.create(payload or TaskCreate())


@router.get("", response_model=list[Task])
def list_tasks() -> list[Task]:
    """List all in-memory tasks."""
    return task_service.list_tasks()


@router.get("/{task_id}", response_model=Task)
def get_task(task_id: UUID) -> Task:
    """Return a single task by ID (404 if missing)."""
    return task_service.get(task_id)


@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: UUID, payload: TaskUpdate) -> Task:
    """Update only the status of an existing task."""
    if payload.status is None:
        raise ValidationError("Field 'status' is required")
    return task_service.update_status(task_id, payload.status)
