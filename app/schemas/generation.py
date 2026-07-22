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
    template_id: str | None = None
    result_transfer_status: TransferStatus | None = None
    result_urls: list[str] | None = None
    failure_code: str | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class CreateGenerationBody(BaseModel):
    job_type: TaskType = Field(
        description=(
            "FAST_IMAGE | PRO_IMAGE | FAST_IMAGE_TO_IMAGE | PRO_IMAGE_TO_IMAGE "
            "| TEXT_VIDEO | IMAGE_VIDEO | DANCE_VIDEO"
        )
    )
    prompt: str | None = None
    aspect_ratio: str = Field(
        default="9:16",
        description=(
            "Default 9:16 (mobile-first). Dance: must match reference video (nodes 451/450)."
        ),
    )
    # Video options; resolution also used by PRO_IMAGE_TO_IMAGE (1k|2k|4k)
    length: int | None = Field(default=None, description="Video length seconds: 5 | 10")
    resolution: str | None = Field(
        default=None,
        description=(
            "Video: 480p|720p|1080p; PRO_IMAGE_TO_IMAGE: 1k|2k|4k (default 2k)"
        ),
    )
    generate_audio: bool | None = Field(
        default=None,
        description="Pollo video only: generate soundtrack (4× credits when true). Default false.",
    )
    input_asset_id: str | None = Field(
        default=None,
        description=(
            "Required for IMAGE_VIDEO / FAST_IMAGE_TO_IMAGE / PRO_IMAGE_TO_IMAGE / DANCE_VIDEO "
            "(S3-ready input image / dance photo)"
        ),
    )
    template_id: str | None = Field(
        default=None,
        description="DANCE_VIDEO: preset template id (node 275). Mutually exclusive with reference_video_asset_id.",
    )
    reference_video_asset_id: str | None = Field(
        default=None,
        description=(
            "DANCE_VIDEO: user-uploaded reference video asset (node 275). "
            "Mutually exclusive with template_id."
        ),
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


class GenerationJobOptions(BaseModel):
    """Frontend-facing option lists for a single job_type (dropdowns, defaults)."""

    job_type: TaskType
    aspect_ratios: list[str]
    default_aspect_ratio: str
    resolutions: list[str] | None = None
    default_resolution: str | None = None
    requires_input_asset: bool = False
    requires_login: bool = False
    credits_required: int | None = None
    credits_required_member: int | None = None
    uses_fast_daily_quota: bool = False
    # Dance-only hints
    supports_template: bool = False
    supports_reference_video: bool = False


class GenerationOptionsResponse(BaseModel):
    jobs: list[GenerationJobOptions]


class DanceTemplateResponse(BaseModel):
    id: str
    title: str
    duration_seconds: int
    video_url: str
    poster_url: str | None = None
    aspect_ratio: str
    sort_order: int = 0


class DanceTemplatesResponse(BaseModel):
    templates: list[DanceTemplateResponse]


class RunningHubWebhookResponse(BaseModel):
    ok: bool
    job_id: str | None = None
    status: TaskStatus | str | None = None


class PolloWebhookResponse(BaseModel):
    ok: bool
    job_id: str | None = None
    status: TaskStatus | str | None = None
