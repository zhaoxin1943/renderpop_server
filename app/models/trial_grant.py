from datetime import datetime

from sqlalchemy import Column, DateTime, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import CreatedModel


class TrialGrant(CreatedModel, table=True):
    """
    One-time trial eligibility (e.g. verified user, face_swap_image ×1).

    Separate from paid entitlements for clear abuse control / audit.
    """

    __tablename__ = "trial_grants"
    __table_args__ = (UniqueConstraint("user_id", "mode", name="uq_trial_grants_user_mode"),)

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    # face_swap_image (MVP trial scope)
    mode: str = Field(sa_column=Column(String(64), nullable=False))
    # available | consumed | revoked
    status: str = Field(
        default="available",
        sa_column=Column(String(32), nullable=False, server_default="available", index=True),
    )
    consumed_job_id: str | None = Field(
        default=None,
        sa_column=Column(String(36), nullable=True),
    )
    entitlement_id: str | None = Field(
        default=None,
        foreign_key="entitlements.id",
        max_length=36,
        nullable=True,
    )
    consumed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
