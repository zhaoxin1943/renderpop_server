"""Dev-only endpoint shapes (non-production)."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.schemas.credit import CreditBalanceResponse


class DevUserBody(BaseModel):
    email: EmailStr
    display_name: str | None = None


class DevUserResponse(BaseModel):
    id: str
    email: str
    created: bool


class GrantCreditsBody(BaseModel):
    user_id: str
    amount: int = Field(gt=0, le=100_000)
    reason: str = "dev_grant"


class GrantCreditsResponse(BaseModel):
    grant_id: str
    balance: CreditBalanceResponse
