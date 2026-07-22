from fastapi import APIRouter, Query

from app.core.deps import ShowcaseServiceDep
from app.schemas.showcase import ShowcaseListResponse

router = APIRouter(prefix="/v1/showcase", tags=["showcase"])


@router.get("", response_model=ShowcaseListResponse)
async def list_showcase(
    service: ShowcaseServiceDep,
    limit: int = Query(default=24, ge=1, le=48),
) -> ShowcaseListResponse:
    """Public curated examples for the homepage waterfall (order randomized per request)."""
    return await service.list_active(limit=limit)
