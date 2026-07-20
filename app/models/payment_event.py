from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import CreatedModel


class PaymentEvent(CreatedModel, table=True):
    """Idempotent webhook / payment provider events."""

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
    event_type: str = Field(sa_column=Column(String(128), nullable=False))
    payload: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    processed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
