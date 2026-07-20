from sqlalchemy import Column, Integer, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import TimestampedModel


class Order(TimestampedModel, table=True):
    """
    Checkout order.

    Status (architecture):
      pending → paid → entitlement_granted → consumed
                     └→ refund_pending → refunded
      pending → expired | failed
    """

    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_orders_idempotency_key"),)

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    product_id: str = Field(foreign_key="products.id", index=True, max_length=36, nullable=False)
    status: str = Field(
        default="pending",
        sa_column=Column(String(32), nullable=False, server_default="pending", index=True),
    )
    amount_cents: int = Field(sa_column=Column(Integer, nullable=False))
    currency: str = Field(sa_column=Column(String(3), nullable=False, server_default="USD"))
    # dodo | …
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
    idempotency_key: str = Field(sa_column=Column(String(128), nullable=False))
