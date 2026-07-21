"""Development-only helpers (auth/login placeholder)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException

from app.core.deps import CreditServiceDep, SettingsDep, UserRepoDep
from app.models.base import new_id
from app.models.user import User
from app.schemas.dev import (
    DevUserBody,
    DevUserResponse,
    GrantCreditsBody,
    GrantCreditsResponse,
)

router = APIRouter(prefix="/v1/dev", tags=["dev"])


@router.post("/users", response_model=DevUserResponse)
async def create_dev_user(
    body: DevUserBody,
    settings: SettingsDep,
    users: UserRepoDep,
) -> DevUserResponse:
    if not settings.is_development:
        raise HTTPException(status_code=404, detail="Not found")
    existing = await users.get_by_email(str(body.email).lower())
    if existing:
        return DevUserResponse(id=existing.id, email=existing.email, created=False)
    user = User(
        id=new_id(),
        email=str(body.email).lower(),
        display_name=body.display_name,
        status="ACTIVE",
        risk_level="LOW",
    )
    await users.create(user)
    return DevUserResponse(id=user.id, email=user.email, created=True)


@router.post("/grant-credits", response_model=GrantCreditsResponse)
async def grant_credits(
    body: GrantCreditsBody,
    settings: SettingsDep,
    credits: CreditServiceDep,
) -> GrantCreditsResponse:
    if not settings.is_development:
        raise HTTPException(status_code=404, detail="Not found")

    grant = await credits._grant(  # noqa: SLF001 — dev only
        user_id=body.user_id,
        grant_type="COMPENSATION",
        amount=body.amount,
        expires_at=datetime.now(UTC) + timedelta(days=90),
        source_type="ADMIN",
        source_id=new_id(),
        idempotency_key=f"dev_grant:{body.user_id}:{new_id()}",
        metadata={"reason": body.reason},
    )
    balance = await credits.get_balance(body.user_id)
    return GrantCreditsResponse(grant_id=grant.id, balance=balance)
