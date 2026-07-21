"""Current-user and entitlements API shapes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.credit import CreditBalanceResponse


class UserSummary(BaseModel):
    id: str


class MeResponse(BaseModel):
    authenticated: bool
    user: UserSummary | None = None
    auth_note: str | None = None


class FastImageQuotaResponse(BaseModel):
    daily_limit: int
    used: int
    remaining: int
    resets_at: datetime


class EntitlementsResponse(BaseModel):
    plan: str
    membership_active: bool
    current_period_end: datetime | None = None
    fast_image: FastImageQuotaResponse
    credits: CreditBalanceResponse
    concurrent_job_limit: int = Field(description="Max concurrent generation jobs for this plan")
