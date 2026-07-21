from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Integer, String
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TimestampedModel


class Asset(SoftDeleteMixin, TimestampedModel, table=True):
    """Private media in S3 (uploads, results). Transfer logic may be stubbed."""

    __tablename__ = "assets"

    owner_user_id: str | None = Field(
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
    # INPUT_IMAGE | OUTPUT_IMAGE | OUTPUT_VIDEO | THUMBNAIL
    asset_type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    # Only object key; never permanent public URL
    storage_key: str | None = Field(default=None, sa_column=Column(String(1024), nullable=True))
    # Temporary provider URL before transfer (24h RH links)
    source_url: str | None = Field(default=None, sa_column=Column(String(2048), nullable=True))
    mime_type: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    byte_size: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    width: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    height: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    checksum_sha256: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    # UPLOADING | READY | PENDING_TRANSFER | QUARANTINED | DELETED
    status: str = Field(
        default="PENDING_TRANSFER",
        sa_column=Column(String(32), nullable=False, server_default="PENDING_TRANSFER", index=True),
    )
    retention_until: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
