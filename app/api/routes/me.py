from typing import Annotated

from fastapi import APIRouter, Header

from app.core.deps import (
    AuthServiceDep,
    CreditServiceDep,
    EntitlementServiceDep,
    OptionalUserIdDep,
    UserIdDep,
)
from app.schemas.credit import CreditTransactionListResponse
from app.schemas.me import EntitlementsResponse, MeResponse

router = APIRouter(prefix="/v1", tags=["me"])


@router.get("/me", response_model=MeResponse)
async def me(user_id: OptionalUserIdDep, auth: AuthServiceDep) -> MeResponse:
    return await auth.get_me(user_id)


@router.get("/me/entitlements", response_model=EntitlementsResponse)
async def entitlements(
    user_id: OptionalUserIdDep,
    service: EntitlementServiceDep,
    x_visitor_id: Annotated[str | None, Header(alias="X-Visitor-Id")] = None,
) -> EntitlementsResponse:
    """Quota for the current user, or visitor Fast daily limit via X-Visitor-Id."""
    return await service.get_entitlements(
        user_id=user_id,
        visitor_id=None if user_id else x_visitor_id,
    )


@router.get("/me/credit-transactions", response_model=CreditTransactionListResponse)
async def credit_transactions(
    user_id: UserIdDep,
    service: CreditServiceDep,
    limit: int = 50,
    offset: int = 0,
) -> CreditTransactionListResponse:
    items = await service.list_transactions(user_id, limit=min(limit, 100), offset=offset)
    return CreditTransactionListResponse(items=items)
