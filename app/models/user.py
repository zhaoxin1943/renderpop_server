from sqlalchemy import Boolean, Column, String
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TimestampedModel


class User(SoftDeleteMixin, TimestampedModel, table=True):
    """Account root. OAuth subjects live in ``identities``."""

    __tablename__ = "users"

    email: str = Field(sa_column=Column(String(320), unique=True, nullable=False, index=True))
    display_name: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    avatar_url: str | None = Field(default=None, sa_column=Column(String(1024), nullable=True))
    # ACTIVE | SUSPENDED
    status: str = Field(
        default="ACTIVE",
        sa_column=Column(String(32), nullable=False, server_default="ACTIVE", index=True),
    )
    # LOW | MEDIUM | HIGH | BLOCKED
    risk_level: str = Field(
        default="LOW",
        sa_column=Column(String(32), nullable=False, server_default="LOW"),
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="1"),
    )
