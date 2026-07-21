from sqlalchemy import Boolean, Column, Integer, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TimestampedModel


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

    # CREATOR_MONTHLY | PRO_MONTHLY | CREDIT_400 | …
    code: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    name: str = Field(sa_column=Column(String(255), nullable=False))
    # SUBSCRIPTION | CREDIT_PACK
    product_type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    # sandbox | live  (Dodo test_mode vs live_mode)
    environment: str = Field(
        default="sandbox",
        sa_column=Column(String(16), nullable=False, server_default="sandbox", index=True),
    )
    # CREATOR | PRO | null for credit packs
    plan_code: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    # month | null
    billing_interval: str | None = Field(
        default=None,
        sa_column=Column(String(16), nullable=True),
    )
    # Credits granted once per successful charge / period
    credits_granted: int = Field(sa_column=Column(Integer, nullable=False, server_default="0"))
    amount_minor: int = Field(sa_column=Column(Integer, nullable=False))
    currency: str = Field(
        default="USD",
        sa_column=Column(String(3), nullable=False, server_default="USD"),
    )
    # Dodo product id (editable per environment)
    provider: str = Field(
        default="dodo",
        sa_column=Column(String(32), nullable=False, server_default="dodo"),
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
