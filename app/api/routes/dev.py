"""Development-only helpers (auth/login placeholder)."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import DevServiceDep
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
    service: DevServiceDep,
) -> DevUserResponse:
    return await service.create_user(
        email=str(body.email),
        display_name=body.display_name,
    )


@router.post("/grant-credits", response_model=GrantCreditsResponse)
async def grant_credits(
    body: GrantCreditsBody,
    service: DevServiceDep,
) -> GrantCreditsResponse:
    return await service.grant_credits(
        user_id=body.user_id,
        amount=body.amount,
        reason=body.reason,
    )
