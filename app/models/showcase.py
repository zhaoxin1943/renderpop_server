"""Curated homepage showcase images (ops-managed, not UGC)."""

from sqlalchemy import Boolean, Column, Integer, String, Text
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TimestampedModel


class ShowcaseItem(SoftDeleteMixin, TimestampedModel, table=True):
    """
    Premium examples shown in the homepage waterfall.

    Clicking an item fills the generator prompt (Try this).
    """

    __tablename__ = "showcase_items"

    title: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    prompt: str = Field(sa_column=Column(Text, nullable=False))
    image_url: str = Field(sa_column=Column(String(1024), nullable=False))
    storage_key: str | None = Field(
        default=None,
        sa_column=Column(String(512), nullable=True, index=True),
    )
    aspect_ratio: str = Field(
        default="9:16",
        sa_column=Column(String(16), nullable=False, server_default="9:16"),
    )
    width: int | None = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
    )
    height: int | None = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
    )
    sort_order: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0", index=True),
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="1", index=True),
    )
