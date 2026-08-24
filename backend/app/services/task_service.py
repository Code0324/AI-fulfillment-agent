"""In-memory generic task service.

Provides basic CRUD-style operations for generic application tasks.
Intentionally has no database, external APIs, workers, or automation —
data lives only for the lifetime of the process.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import math

from app.core.errors import NotFoundError
from app.schemas.task import Task, TaskCreate, TaskListResponse, TaskStatus


class TaskService:
    """In-memory store and operations for generic tasks."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, Task] = {}

    def create(self, payload: TaskCreate) -> Task:
        """Create a new task with the requested initial status."""
        now = datetime.now(timezone.utc)
        task = Task(
            id=uuid4(),
            title=payload.title,
            status=payload.status,
            created_at=now,
            updated_at=now,
        )
        self._tasks[task.id] = task
        return task

    def get(self, task_id: UUID) -> Task:
        """Return one task by ID or raise NotFoundError."""
        task = self._tasks.get(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        return task

    def list_tasks(self) -> list[Task]:
        """Return all in-memory tasks (insertion order)."""
        return list(self._tasks.values())

    def list_tasks_paginated(
        self, *, page: int = 1, page_size: int = 10
    ) -> TaskListResponse:
        """Return a paginated slice of tasks with metadata."""
        all_tasks = list(self._tasks.values())
        total_items = len(all_tasks)
        total_pages = math.ceil(total_items / page_size) if total_items else 0

        start = (page - 1) * page_size
        end = start + page_size
        items = all_tasks[start:end]

        return TaskListResponse(
            items=items,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )

    def update_status(self, task_id: UUID, status: TaskStatus) -> Task:
        """Update only the status of an existing task."""
        task = self.get(task_id)
        updated = task.model_copy(
            update={
                "status": status,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._tasks[task_id] = updated
        return updated

    def clear(self) -> None:
        """Remove all tasks (used by tests to reset state)."""
        self._tasks.clear()


task_service = TaskService()
