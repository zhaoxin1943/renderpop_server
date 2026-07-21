from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import TimestampedModel


class Subscription(TimestampedModel, table=True):
    """
    Monthly membership subscription (Creator / Pro).

    Status (mapped from Dodo):
      INCOMPLETE | ACTIVE | ON_HOLD | CANCELED | EXPIRED | FAILED
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_subscriptions_provider_sub",
        ),
    )

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    # CREATOR | PRO
    plan_code: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    product_code: str = Field(sa_column=Column(String(64), nullable=False))
    provider: str = Field(
        default="dodo",
        sa_column=Column(String(32), nullable=False, server_default="dodo"),
    )
    provider_customer_id: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, index=True),
    )
    provider_subscription_id: str = Field(sa_column=Column(String(255), nullable=False))
    status: str = Field(
        default="INCOMPLETE",
        sa_column=Column(String(32), nullable=False, server_default="INCOMPLETE", index=True),
    )
    current_period_start: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    current_period_end: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    cancel_at_period_end: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="0"),
    )
    canceled_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    ended_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_synced_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
