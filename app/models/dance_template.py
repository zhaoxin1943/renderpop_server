"""Preset dance video templates catalog."""

from sqlalchemy import Boolean, Column, Integer, String
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TimestampedModel


class DanceTemplate(SoftDeleteMixin, TimestampedModel, table=True):
    """Preset dance video templates for AI motion control."""

    __tablename__ = "dance_templates"

    id: str = Field(
        sa_column=Column(String(64), primary_key=True, nullable=False)
    )
    title: str = Field(
        sa_column=Column(String(128), nullable=False)
    )
    duration_seconds: int = Field(
        sa_column=Column(Integer, nullable=False, server_default="10")
    )
    video_url: str = Field(
        sa_column=Column(String(1024), nullable=False)
    )
    poster_url: str | None = Field(
        default=None,
        sa_column=Column(String(1024), nullable=True)
    )
    aspect_ratio: str = Field(
        default="9:16",
        sa_column=Column(String(16), nullable=False, server_default="9:16")
    )
    sort_order: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0", index=True)
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="1", index=True)
    )
    is_trending: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="0", index=True)
    )
    category: str = Field(
        default="general",
        sa_column=Column(String(32), nullable=False, server_default="general", index=True)
    )
