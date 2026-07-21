from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import TimestampedModel


class Order(TimestampedModel, table=True):
    """
    Checkout order for subscription or credit pack.

    Status: PENDING | PAID | FAILED | REFUNDED | PARTIALLY_REFUNDED | EXPIRED
    """

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_idempotency"),
    )

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    # SUBSCRIPTION | CREDIT_PACK
    order_type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    status: str = Field(
        default="PENDING",
        sa_column=Column(String(32), nullable=False, server_default="PENDING", index=True),
    )
    product_code: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    product_id: str = Field(foreign_key="products.id", index=True, max_length=36, nullable=False)
    # Immutable snapshot at checkout time
    product_snapshot: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    amount_minor: int = Field(sa_column=Column(Integer, nullable=False))
    currency: str = Field(sa_column=Column(String(3), nullable=False, server_default="USD"))
    payment_provider: str = Field(
        default="dodo",
        sa_column=Column(String(32), nullable=False, server_default="dodo"),
    )
    provider_checkout_id: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, index=True),
    )
    provider_payment_id: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, index=True),
    )
    provider_subscription_id: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, index=True),
    )
    idempotency_key: str = Field(sa_column=Column(String(128), nullable=False))
    paid_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    refunded_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
