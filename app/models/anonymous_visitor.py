from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field

from app.models.base import CreatedModel, utc_now


class AnonymousVisitor(CreatedModel, table=True):
    """Anonymous visitor for Fast free quota (cookie id)."""

    __tablename__ = "anonymous_visitors"

    # SHA-256 hex of IP (no plaintext permanent storage)
    first_ip_hash: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    device_hash: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    merged_user_id: str | None = Field(
        default=None,
        foreign_key="users.id",
        max_length=36,
        nullable=True,
        index=True,
    )
    last_seen_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
