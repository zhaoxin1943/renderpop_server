from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlmodel import Field

from app.models.base import CreatedModel, TimestampedModel


class GenerationTask(TimestampedModel, table=True):
    """
    Image generation task (Fast / Pro). Dance reserved for later.

    User inputs + RunningHub provider fields + result linkage.
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
    # FAST_IMAGE | PRO_IMAGE | DANCE_VIDEO (future)
    task_type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    # CREATED | MODERATING | QUEUED | SUBMITTING | PROCESSING |
    # SUCCEEDED | REJECTED | FAILED | CANCEL_REQUESTED | CANCELED | EXPIRED
    status: str = Field(
        default="CREATED",
        sa_column=Column(String(32), nullable=False, server_default="CREATED", index=True),
    )
    prompt: str = Field(sa_column=Column(Text, nullable=False))
    aspect_ratio: str = Field(sa_column=Column(String(16), nullable=False))
    # width/height/scale_by or quality/resolution snapshot
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
    provider: str | None = Field(
        default="runninghub",
        sa_column=Column(String(64), nullable=True),
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
    # PENDING | SKIPPED | SUCCEEDED | FAILED  (S3 transfer; stub for now)
    result_transfer_status: str = Field(
        default="PENDING",
        sa_column=Column(String(32), nullable=False, server_default="PENDING"),
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
    # submitted | running | succeeded | failed | timed_out
    status: str = Field(sa_column=Column(String(32), nullable=False, index=True))
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
