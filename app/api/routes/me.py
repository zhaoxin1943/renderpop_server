from typing import Any

from fastapi import APIRouter

from app.core.deps import (
    CreditServiceDep,
    EntitlementServiceDep,
    OptionalUserIdDep,
    UserIdDep,
)

router = APIRouter(prefix="/v1", tags=["me"])


@router.get("/me")
async def me(user_id: OptionalUserIdDep) -> dict[str, Any]:
    if not user_id:
        return {"authenticated": False, "user": None}
    return {
        "authenticated": True,
        "user": {"id": user_id},
        "auth_note": "placeholder — Google OAuth not wired",
    }


@router.get("/me/entitlements")
async def entitlements(
    user_id: OptionalUserIdDep,
    service: EntitlementServiceDep,
) -> dict[str, Any]:
    return await service.get_entitlements(user_id=user_id, visitor_id=None)


@router.get("/me/credit-transactions")
async def credit_transactions(
    user_id: UserIdDep,
    service: CreditServiceDep,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    items = await service.list_transactions(user_id, limit=min(limit, 100), offset=offset)
    return {"items": items}
