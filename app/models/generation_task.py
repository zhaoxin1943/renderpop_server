from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlmodel import Field

from app.models.base import CreatedModel, TimestampedModel
from app.models.enums import (
    AttemptStatus,
    GenerationProvider,
    TaskStatus,
    TaskType,
    TransferStatus,
    sa_str_enum,
)


class GenerationTask(TimestampedModel, table=True):
    """
    Generation task (Fast/Pro image, AI video). Dance reserved for later.

    User inputs + provider fields + result linkage.
    """

    __tablename__ = "generation_tasks"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_generation_tasks_idempotency"),
    )

    user_id: str | None = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        max_length=36,
        nullable=True,
    )
    visitor_id: str | None = Field(
        default=None,
        foreign_key="anonymous_visitors.id",
        index=True,
        max_length=36,
        nullable=True,
    )
    task_type: TaskType = Field(sa_column=Column(sa_str_enum(TaskType), nullable=False, index=True))
    status: TaskStatus = Field(
        default=TaskStatus.CREATED,
        sa_column=Column(
            sa_str_enum(TaskStatus),
            nullable=False,
            server_default=TaskStatus.CREATED.value,
            index=True,
        ),
    )
    prompt: str = Field(sa_column=Column(Text, nullable=False))
    aspect_ratio: str = Field(sa_column=Column(String(16), nullable=False))
    # Catalog model used for this job (video); null for legacy image rows
    model_id: str | None = Field(
        default=None,
        foreign_key="generation_models.id",
        max_length=36,
        nullable=True,
        index=True,
    )
    model_code: str | None = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
    )
    # IMAGE_VIDEO input photo
    input_asset_id: str | None = Field(
        default=None,
        foreign_key="assets.id",
        max_length=36,
        nullable=True,
        index=True,
    )
    # width/height/scale_by or quality/resolution/length snapshot
    input_params: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    pricing_snapshot: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    credits_reserved: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    credit_reservation_id: str | None = Field(
        default=None,
        sa_column=Column(String(36), nullable=True, index=True),
    )
    provider: GenerationProvider | None = Field(
        default=GenerationProvider.RUNNINGHUB,
        sa_column=Column(sa_str_enum(GenerationProvider, length=64), nullable=True),
    )
    provider_app_id: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    provider_task_id: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, index=True),
    )
    provider_status: str | None = Field(
        default=None,
        sa_column=Column(String(32), nullable=True, index=True),
    )
    provider_usage: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    provider_raw_result: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    result_asset_id: str | None = Field(
        default=None,
        foreign_key="assets.id",
        max_length=36,
        nullable=True,
    )
    result_transfer_status: TransferStatus = Field(
        default=TransferStatus.PENDING,
        sa_column=Column(
            sa_str_enum(TransferStatus),
            nullable=False,
            server_default=TransferStatus.PENDING.value,
        ),
    )
    failure_code: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    failure_detail: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    attempt_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    idempotency_key: str = Field(sa_column=Column(String(128), nullable=False))
    submitted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class GenerationAttempt(CreatedModel, table=True):
    """One provider submit/poll cycle for a generation task."""

    __tablename__ = "generation_attempts"
    __table_args__ = (
        UniqueConstraint("task_id", "attempt_no", name="uq_generation_attempts_task_attempt"),
    )

    task_id: str = Field(
        foreign_key="generation_tasks.id",
        index=True,
        max_length=36,
        nullable=False,
    )
    attempt_no: int = Field(sa_column=Column(Integer, nullable=False))
    status: AttemptStatus = Field(
        sa_column=Column(sa_str_enum(AttemptStatus), nullable=False, index=True)
    )
    provider_task_id: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    request_meta: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    response_meta: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    finished_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
