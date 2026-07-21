from sqlalchemy import Boolean, Column, Integer, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TimestampedModel
from app.models.enums import (
    BillingInterval,
    MembershipPlan,
    PaymentProvider,
    ProductEnvironment,
    ProductType,
    sa_str_enum,
)


class Product(SoftDeleteMixin, TimestampedModel, table=True):
    """
    Server-side SKU catalog.

    Exactly 5 MVP SKUs (per environment):
      CREATOR_MONTHLY, PRO_MONTHLY, CREDIT_400, CREDIT_900, CREDIT_2000
    """

    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("environment", "code", name="uq_products_env_code"),
        UniqueConstraint(
            "environment",
            "provider_product_id",
            name="uq_products_env_provider_product",
        ),
    )

    code: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    name: str = Field(sa_column=Column(String(255), nullable=False))
    product_type: ProductType = Field(
        sa_column=Column(sa_str_enum(ProductType), nullable=False, index=True)
    )
    environment: ProductEnvironment = Field(
        default=ProductEnvironment.SANDBOX,
        sa_column=Column(
            sa_str_enum(ProductEnvironment, length=16),
            nullable=False,
            server_default=ProductEnvironment.SANDBOX.value,
            index=True,
        ),
    )
    plan_code: MembershipPlan | None = Field(
        default=None,
        sa_column=Column(sa_str_enum(MembershipPlan), nullable=True),
    )
    billing_interval: BillingInterval | None = Field(
        default=None,
        sa_column=Column(sa_str_enum(BillingInterval, length=16), nullable=True),
    )
    # Credits granted once per successful charge / period
    credits_granted: int = Field(sa_column=Column(Integer, nullable=False, server_default="0"))
    amount_minor: int = Field(sa_column=Column(Integer, nullable=False))
    currency: str = Field(
        default="USD",
        sa_column=Column(String(3), nullable=False, server_default="USD"),
    )
    provider: PaymentProvider = Field(
        default=PaymentProvider.DODO,
        sa_column=Column(
            sa_str_enum(PaymentProvider),
            nullable=False,
            server_default=PaymentProvider.DODO.value,
        ),
    )
    provider_product_id: str = Field(sa_column=Column(String(128), nullable=False))
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="1"),
    )
    config_version: str = Field(
        default="1",
        sa_column=Column(String(32), nullable=False, server_default="1"),
    )
