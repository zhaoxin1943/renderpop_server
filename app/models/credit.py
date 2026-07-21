from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import CreatedModel, TimestampedModel
from app.models.enums import (
    CreditGrantStatus,
    CreditGrantType,
    CreditReservationStatus,
    CreditSourceType,
    CreditTxnType,
    sa_str_enum,
)


class CreditGrant(TimestampedModel, table=True):
    """
    One-shot credit batch (signup, subscription period, pack, promo, admin).

    Invariant:
      original_amount = available + reserved + consumed + revoked
    """

    __tablename__ = "credit_grants"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_credit_grants_idempotency"),
    )

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    grant_type: CreditGrantType = Field(
        sa_column=Column(sa_str_enum(CreditGrantType), nullable=False, index=True)
    )
    original_amount: int = Field(sa_column=Column(Integer, nullable=False))
    available_amount: int = Field(sa_column=Column(Integer, nullable=False))
    reserved_amount: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    consumed_amount: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    revoked_amount: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    source_type: CreditSourceType = Field(
        sa_column=Column(sa_str_enum(CreditSourceType), nullable=False, index=True)
    )
    source_id: str | None = Field(
        default=None,
        sa_column=Column(String(64), nullable=True, index=True),
    )
    idempotency_key: str = Field(sa_column=Column(String(191), nullable=False))
    status: CreditGrantStatus = Field(
        default=CreditGrantStatus.ACTIVE,
        sa_column=Column(
            sa_str_enum(CreditGrantStatus),
            nullable=False,
            server_default=CreditGrantStatus.ACTIVE.value,
            index=True,
        ),
    )


class CreditTransaction(CreatedModel, table=True):
    """Immutable credit ledger. All balance changes append here."""

    __tablename__ = "credit_transactions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_credit_transactions_idempotency"),
    )

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    grant_id: str = Field(
        foreign_key="credit_grants.id",
        index=True,
        max_length=36,
        nullable=False,
    )
    generation_task_id: str | None = Field(
        default=None,
        sa_column=Column(String(36), nullable=True, index=True),
    )
    type: CreditTxnType = Field(
        sa_column=Column(sa_str_enum(CreditTxnType), nullable=False, index=True)
    )
    # Always positive; direction is implied by type
    amount: int = Field(sa_column=Column(Integer, nullable=False))
    balance_after: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    idempotency_key: str = Field(sa_column=Column(String(191), nullable=False))
    metadata_json: dict | None = Field(
        default=None,
        sa_column=Column("metadata", JSON, nullable=True),
    )


class CreditReservation(TimestampedModel, table=True):
    """Task-level hold across one or more grants (FEFO)."""

    __tablename__ = "credit_reservations"
    __table_args__ = (
        UniqueConstraint("generation_task_id", name="uq_credit_reservations_task"),
    )

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    generation_task_id: str = Field(sa_column=Column(String(36), nullable=False))
    total_amount: int = Field(sa_column=Column(Integer, nullable=False))
    status: CreditReservationStatus = Field(
        default=CreditReservationStatus.ACTIVE,
        sa_column=Column(
            sa_str_enum(CreditReservationStatus),
            nullable=False,
            server_default=CreditReservationStatus.ACTIVE.value,
            index=True,
        ),
    )
    expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    pricing_snapshot: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))


class CreditReservationItem(CreatedModel, table=True):
    """Per-grant slice of a reservation."""

    __tablename__ = "credit_reservation_items"

    reservation_id: str = Field(
        foreign_key="credit_reservations.id",
        index=True,
        max_length=36,
        nullable=False,
    )
    grant_id: str = Field(
        foreign_key="credit_grants.id",
        index=True,
        max_length=36,
        nullable=False,
    )
    amount: int = Field(sa_column=Column(Integer, nullable=False))
