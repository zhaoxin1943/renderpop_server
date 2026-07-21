from sqlalchemy import Column, String, UniqueConstraint
from sqlmodel import Field

from app.models.base import CreatedModel
from app.models.enums import IdentityProvider, sa_str_enum


class Identity(CreatedModel, table=True):
    """External identity linked to a user (Google, email OTP, …)."""

    __tablename__ = "identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_identities_provider_subject"),
    )

    user_id: str = Field(foreign_key="users.id", index=True, max_length=36, nullable=False)
    provider: IdentityProvider = Field(
        sa_column=Column(sa_str_enum(IdentityProvider), nullable=False, index=True)
    )
    provider_subject: str = Field(sa_column=Column(String(255), nullable=False))
    email: str | None = Field(default=None, sa_column=Column(String(320), nullable=True))
