from sqlalchemy import Boolean, Column, String
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TimestampedModel
from app.models.enums import RiskLevel, UserStatus, sa_str_enum


class User(SoftDeleteMixin, TimestampedModel, table=True):
    """Account root. OAuth subjects live in ``identities``."""

    __tablename__ = "users"

    email: str = Field(sa_column=Column(String(320), unique=True, nullable=False, index=True))
    display_name: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    avatar_url: str | None = Field(default=None, sa_column=Column(String(1024), nullable=True))
    status: UserStatus = Field(
        default=UserStatus.ACTIVE,
        sa_column=Column(
            sa_str_enum(UserStatus),
            nullable=False,
            server_default=UserStatus.ACTIVE.value,
            index=True,
        ),
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.LOW,
        sa_column=Column(
            sa_str_enum(RiskLevel),
            nullable=False,
            server_default=RiskLevel.LOW.value,
        ),
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="1"),
    )
