"""
Shared SQLModel mixins for domain tables.

Usage:
  class User(SoftDeleteMixin, TimestampedModel, table=True): ...
  class PaymentEvent(CreatedModel, table=True): ...   # append-only

Soft-delete is opt-in via SoftDeleteMixin — do NOT hang it on ledgers/events.
Filter live rows with: ``Model.deleted_at.is_(None)``.

Note: use ``sa_type`` + ``sa_column_kwargs`` (not a shared ``Column()`` instance)
so each concrete table gets its own SQLAlchemy Column objects.
"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, func
from sqlmodel import Field, SQLModel


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class IdMixin(SQLModel):
    """Primary key: UUID string (CHAR(36))."""

    id: str = Field(
        default_factory=new_id,
        sa_type=String(36),
        sa_column_kwargs={"primary_key": True},
    )


class CreatedAtMixin(SQLModel):
    """Insert-only timestamp (append-only rows)."""

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"server_default": func.now(), "nullable": False},
    )


class UpdatedAtMixin(SQLModel):
    """Row last-update timestamp."""

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": func.now(),
            "nullable": False,
        },
    )


class SoftDeleteMixin(SQLModel):
    """
    Soft delete via nullable ``deleted_at`` (preferred over a bool flag).

    - Live: deleted_at IS NULL
    - Soft-deleted: deleted_at = UTC when deleted
    - Restore: set deleted_at back to NULL
    """

    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"nullable": True, "index": True},
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class CreatedModel(IdMixin, CreatedAtMixin):
    """id + created_at — ledger / events / attempts / identities."""


class TimestampedModel(IdMixin, CreatedAtMixin, UpdatedAtMixin):
    """id + created_at + updated_at — most mutable domain tables."""
