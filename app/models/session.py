from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text
from sqlmodel import Field

from app.models.base import TimestampedModel


class Session(TimestampedModel, table=True):
    """Server-side session. Cookie holds opaque token; DB stores hash only."""

    __tablename__ = "sessions"

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    token_hash: str = Field(sa_column=Column(String(64), unique=True, nullable=False, index=True))
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    ip: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    user_agent: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
