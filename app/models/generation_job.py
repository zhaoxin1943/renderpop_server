from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlmodel import Field

from app.models.base import CreatedModel, TimestampedModel


class GenerationJob(TimestampedModel, table=True):
    """
    AI generation job.

    Status (architecture):
      created → awaiting_entitlement → queued → running → transferring → succeeded
                                       └→ failed → compensated
    """

    __tablename__ = "generation_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_generation_jobs_idempotency"),
    )

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    # face_swap_image | face_swap_video | dance
    mode: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    status: str = Field(
        default="created",
        sa_column=Column(String(32), nullable=False, server_default="created", index=True),
    )
    entitlement_id: str | None = Field(
        default=None,
        foreign_key="entitlements.id",
        index=True,
        max_length=36,
        nullable=True,
    )
    # Template key for dance / preset, optional
    template_id: str | None = Field(
        default=None,
        sa_column=Column(String(128), nullable=True, index=True),
    )
    source_asset_id: str | None = Field(
        default=None,
        foreign_key="assets.id",
        max_length=36,
        nullable=True,
    )
    target_asset_id: str | None = Field(
        default=None,
        foreign_key="assets.id",
        max_length=36,
        nullable=True,
    )
    result_asset_id: str | None = Field(
        default=None,
        foreign_key="assets.id",
        max_length=36,
        nullable=True,
    )
    # runninghub | …
    provider: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    provider_task_id: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, index=True),
    )
    error_code: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    meta: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    idempotency_key: str = Field(sa_column=Column(String(128), nullable=False))
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class GenerationAttempt(CreatedModel, table=True):
    """One provider attempt / poll cycle for a job (retries, audit)."""

    __tablename__ = "generation_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_no", name="uq_generation_attempts_job_attempt"),
    )

    job_id: str = Field(
        foreign_key="generation_jobs.id",
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
