from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import TimestampedModel
from app.models.enums import MembershipPlan, PaymentProvider, SubscriptionStatus, sa_str_enum


class Subscription(TimestampedModel, table=True):
    """Monthly membership subscription (Creator / Pro). Status mapped from Dodo."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_subscriptions_provider_sub",
        ),
    )

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    plan_code: MembershipPlan = Field(
        sa_column=Column(sa_str_enum(MembershipPlan), nullable=False, index=True)
    )
    product_code: str = Field(sa_column=Column(String(64), nullable=False))
    provider: PaymentProvider = Field(
        default=PaymentProvider.DODO,
        sa_column=Column(
            sa_str_enum(PaymentProvider),
            nullable=False,
            server_default=PaymentProvider.DODO.value,
        ),
    )
    provider_customer_id: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, index=True),
    )
    provider_subscription_id: str = Field(sa_column=Column(String(255), nullable=False))
    status: SubscriptionStatus = Field(
        default=SubscriptionStatus.INCOMPLETE,
        sa_column=Column(
            sa_str_enum(SubscriptionStatus),
            nullable=False,
            server_default=SubscriptionStatus.INCOMPLETE.value,
            index=True,
        ),
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
