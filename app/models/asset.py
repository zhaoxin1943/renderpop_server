from sqlalchemy import BigInteger, Column, String
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TimestampedModel


class Asset(SoftDeleteMixin, TimestampedModel, table=True):
    """Private media in S3 (uploads, results, optional template refs)."""

    __tablename__ = "assets"

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    # image | video
    kind: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    # source | target | result | template
    purpose: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    s3_key: str = Field(sa_column=Column(String(1024), nullable=False))
    content_type: str | None = Field(default=None, sa_column=Column(String(128), nullable=True))
    byte_size: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    checksum_sha256: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))
    # pending | ready | failed (soft-delete uses deleted_at, not status)
    status: str = Field(
        default="pending",
        sa_column=Column(String(32), nullable=False, server_default="pending", index=True),
    )
