from sqlalchemy import Boolean, Column, Integer, String
from sqlmodel import Field

from app.models.base import SoftDeleteMixin, TimestampedModel


class Product(SoftDeleteMixin, TimestampedModel, table=True):
    """Server-side SKU catalog. Client never dictates price."""

    __tablename__ = "products"

    # e.g. face_swap_image_1, dance_single
    code: str = Field(sa_column=Column(String(64), unique=True, nullable=False, index=True))
    name: str = Field(sa_column=Column(String(255), nullable=False))
    # face_swap_image | face_swap_video | dance
    mode: str = Field(sa_column=Column(String(64), nullable=False, index=True))
    # How many generation units this SKU grants
    grant_units: int = Field(sa_column=Column(Integer, nullable=False, server_default="1"))
    price_cents: int = Field(sa_column=Column(Integer, nullable=False))
    currency: str = Field(
        default="USD",
        sa_column=Column(String(3), nullable=False, server_default="USD"),
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default="1"),
    )
