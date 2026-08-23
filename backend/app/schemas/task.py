"""Generic task/job schema for future asynchronous work.

Represents only generic application state — not connected to
Amazon, suppliers, AI, browser automation, or payments.
Future chunks will extend this with domain-specific fields.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Lifecycle states for a generic background task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    """A generic background task.

    Fields are intentionally minimal — just enough to track
    lifecycle. Domain-specific payloads will be added later.
    """

    id: UUID = Field(..., description="Unique task identifier")
    status: TaskStatus = Field(..., description="Current task status")
    created_at: datetime = Field(..., description="When the task was created")
    updated_at: datetime = Field(..., description="When the task was last updated")


class TaskCreate(BaseModel):
    """Payload for creating a new task (future use)."""

    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Initial status")


class TaskUpdate(BaseModel):
    """Payload for updating a task (future use)."""

    status: TaskStatus | None = Field(None, description="New status value")
