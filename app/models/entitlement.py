from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import CreatedModel, TimestampedModel


class Entitlement(TimestampedModel, table=True):
    """Spendable generation balance granted by order / trial / admin."""

    __tablename__ = "entitlements"

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    # order | trial | admin | compensate
    source_type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    source_id: str | None = Field(
        default=None,
        sa_column=Column(String(36), nullable=True, index=True),
    )
    # face_swap_image | face_swap_video | dance
    mode: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    units_total: int = Field(sa_column=Column(Integer, nullable=False))
    units_remaining: int = Field(sa_column=Column(Integer, nullable=False))
    # active | exhausted | revoked | expired
    status: str = Field(
        default="active",
        sa_column=Column(String(32), nullable=False, server_default="active", index=True),
    )
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class EntitlementLedger(CreatedModel, table=True):
    """Immutable unit movements (grant / consume / refund / compensate)."""

    __tablename__ = "entitlement_ledger"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_entitlement_ledger_idempotency"),
    )

    entitlement_id: str = Field(
        foreign_key="entitlements.id",
        index=True,
        max_length=36,
        nullable=False,
    )
    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    # positive = grant, negative = consume
    delta: int = Field(sa_column=Column(Integer, nullable=False))
    # grant | consume | refund | compensate | expire | revoke
    reason: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    job_id: str | None = Field(
        default=None,
        sa_column=Column(String(36), nullable=True, index=True),
    )
    idempotency_key: str = Field(sa_column=Column(String(128), nullable=False))
