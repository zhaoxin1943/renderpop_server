"""Billing / products / checkout public API shapes."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import (
    BillingInterval,
    MembershipPlan,
    OrderStatus,
    ProductEnvironment,
    ProductType,
)


class ProductResponse(BaseModel):
    code: str
    name: str
    product_type: ProductType
    plan_code: MembershipPlan | None = None
    billing_interval: BillingInterval | None = None
    credits_granted: int
    amount_minor: int
    currency: str
    environment: ProductEnvironment | str


class ProductListResponse(BaseModel):
    items: list[ProductResponse]


class CheckoutBody(BaseModel):
    product_code: str
    success_url: str | None = None
    cancel_url: str | None = None


class CheckoutSessionResponse(BaseModel):
    order_id: str
    status: OrderStatus | str
    checkout_url: str | None = None
    session_id: str | None = None
    reused: bool = False
    stub: bool | None = Field(
        default=None,
        description="True when Dodo was not configured and a stub session was returned",
    )


class DodoWebhookResponse(BaseModel):
    ok: bool
    error: str | None = None
    duplicate: bool | None = None
    event_id: str | None = None
    type: str | None = None
