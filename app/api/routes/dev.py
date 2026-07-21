"""Development-only helpers (auth/login placeholder)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core.deps import CreditServiceDep, SessionDep, SettingsDep, UserRepoDep
from app.models.user import User
from app.models.base import new_id

router = APIRouter(prefix="/v1/dev", tags=["dev"])


class DevUserBody(BaseModel):
    email: EmailStr
    display_name: str | None = None


@router.post("/users")
async def create_dev_user(
    body: DevUserBody,
    settings: SettingsDep,
    users: UserRepoDep,
) -> dict[str, Any]:
    if not settings.is_development:
        raise HTTPException(status_code=404, detail="Not found")
    existing = await users.get_by_email(str(body.email).lower())
    if existing:
        return {"id": existing.id, "email": existing.email, "created": False}
    user = User(
        id=new_id(),
        email=str(body.email).lower(),
        display_name=body.display_name,
        status="ACTIVE",
        risk_level="LOW",
    )
    await users.create(user)
    return {"id": user.id, "email": user.email, "created": True}


class GrantCreditsBody(BaseModel):
    user_id: str
    amount: int = Field(gt=0, le=100_000)
    reason: str = "dev_grant"


@router.post("/grant-credits")
async def grant_credits(
    body: GrantCreditsBody,
    settings: SettingsDep,
    credits: CreditServiceDep,
) -> dict[str, Any]:
    if not settings.is_development:
        raise HTTPException(status_code=404, detail="Not found")
    from datetime import UTC, datetime, timedelta

    from app.models.base import new_id as nid

    grant = await credits._grant(  # noqa: SLF001 — dev only
        user_id=body.user_id,
        grant_type="COMPENSATION",
        amount=body.amount,
        expires_at=datetime.now(UTC) + timedelta(days=90),
        source_type="ADMIN",
        source_id=nid(),
        idempotency_key=f"dev_grant:{body.user_id}:{nid()}",
        metadata={"reason": body.reason},
    )
    balance = await credits.get_balance(body.user_id)
    return {"grant_id": grant.id, "balance": balance}
