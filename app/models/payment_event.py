from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import CreatedModel


class PaymentEvent(CreatedModel, table=True):
    """
    Idempotent webhook / payment provider events.

    Unique on (provider, event_id). Process at most once.
    """

    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_payment_events_provider_event"),
    )

    order_id: str | None = Field(
        default=None,
        foreign_key="orders.id",
        index=True,
        max_length=36,
        nullable=True,
    )
    provider: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    event_id: str = Field(sa_column=Column(String(255), nullable=False))
    event_type: str = Field(sa_column=Column(String(128), nullable=False, index=True))
    # RECEIVED | PROCESSING | PROCESSED | FAILED | IGNORED
    status: str = Field(
        default="RECEIVED",
        sa_column=Column(String(32), nullable=False, server_default="RECEIVED", index=True),
    )
    payload: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    attempt_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default="0"),
    )
    processed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    error_message: str | None = Field(default=None, sa_column=Column(String(1024), nullable=True))
