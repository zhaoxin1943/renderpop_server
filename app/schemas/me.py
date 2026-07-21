"""Current-user and entitlements API shapes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import PlanCode
from app.schemas.credit import CreditBalanceResponse


class UserSummary(BaseModel):
    id: str
    email: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None


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
    plan: PlanCode | str
    membership_active: bool
    current_period_end: datetime | None = None
    fast_image: FastImageQuotaResponse
    credits: CreditBalanceResponse
    concurrent_job_limit: int = Field(description="Max concurrent generation jobs for this plan")
