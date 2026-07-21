"""Generation task public API shapes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import TaskStatus, TaskType, TransferStatus


class GenerationTaskResponse(BaseModel):
    job_id: str
    task_type: TaskType
    status: TaskStatus
    aspect_ratio: str
    credits_reserved: int = 0
    result_transfer_status: TransferStatus | None = None
    result_urls: list[str] | None = None
    failure_code: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class CreateGenerationBody(BaseModel):
    job_type: TaskType = Field(description="FAST_IMAGE | PRO_IMAGE")
    prompt: str
    aspect_ratio: str = "1:1"
    client_request_id: str | None = None


class RunningHubWebhookResponse(BaseModel):
    ok: bool
    job_id: str | None = None
    status: TaskStatus | str | None = None
