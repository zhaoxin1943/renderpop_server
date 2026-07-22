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
    length: int | None = None
    resolution: str | None = None
    generate_audio: bool | None = None
    result_transfer_status: TransferStatus | None = None
    result_urls: list[str] | None = None
    failure_code: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class CreateGenerationBody(BaseModel):
    job_type: TaskType = Field(
        description="FAST_IMAGE | PRO_IMAGE | TEXT_VIDEO | IMAGE_VIDEO"
    )
    prompt: str | None = None
    aspect_ratio: str = Field(
        default="9:16", description="Default 9:16 (mobile-first)"
    )
    # Video options (ignored for image jobs)
    length: int | None = Field(default=None, description="Video length seconds: 5 | 10")
    resolution: str | None = Field(
        default=None, description="Video resolution: 480p | 720p | 1080p"
    )
    generate_audio: bool | None = Field(
        default=None,
        description="Video only: generate soundtrack (4× credits when true). Default false.",
    )
    input_asset_id: str | None = Field(
        default=None, description="Required for IMAGE_VIDEO (S3-ready input)"
    )
    client_request_id: str | None = None


class GenerationQuoteBody(BaseModel):
    job_type: TaskType
    length: int | None = None
    resolution: str | None = None
    generate_audio: bool | None = Field(
        default=None,
        description="Video only: include audio mult in quote (default false)",
    )


class GenerationQuoteResponse(BaseModel):
    job_type: TaskType
    credits_required: int
    length: int
    resolution: str
    generate_audio: bool | None = None
    can_generate: bool | None = None
    available_credits: int | None = None
    pricing_version: str | None = None


class RunningHubWebhookResponse(BaseModel):
    ok: bool
    job_id: str | None = None
    status: TaskStatus | str | None = None


class PolloWebhookResponse(BaseModel):
    ok: bool
    job_id: str | None = None
    status: TaskStatus | str | None = None
