from sqlalchemy import Column, Integer, String, Text
from sqlmodel import Field

from app.models.base import TimestampedModel
from app.models.enums import RefundStatus, sa_str_enum


class Refund(TimestampedModel, table=True):
    """Payment refund request / outcome for an order."""

    __tablename__ = "refunds"

    order_id: str = Field(foreign_key="orders.id", index=True, max_length=36, nullable=False)
    status: RefundStatus = Field(
        default=RefundStatus.PENDING,
        sa_column=Column(
            sa_str_enum(RefundStatus),
            nullable=False,
            server_default=RefundStatus.PENDING.value,
            index=True,
        ),
    )
    amount_minor: int = Field(sa_column=Column(Integer, nullable=False))
    currency: str = Field(sa_column=Column(String(3), nullable=False, server_default="USD"))
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    provider_refund_id: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True, index=True),
    )
