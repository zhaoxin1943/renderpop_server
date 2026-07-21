from fastapi import APIRouter, Query

from app.core.deps import SessionDep
from app.repo.showcase_repo import ShowcaseRepo
from app.schemas.showcase import ShowcaseItemResponse, ShowcaseListResponse

router = APIRouter(prefix="/v1/showcase", tags=["showcase"])


@router.get("", response_model=ShowcaseListResponse)
async def list_showcase(
    session: SessionDep,
    limit: int = Query(default=24, ge=1, le=48),
) -> ShowcaseListResponse:
    """Public curated examples for the homepage waterfall."""
    rows = await ShowcaseRepo(session).list_active(limit=limit)
    return ShowcaseListResponse(
        items=[
            ShowcaseItemResponse(
                id=row.id,
                title=row.title,
                prompt=row.prompt,
                image_url=row.image_url,
                aspect_ratio=row.aspect_ratio,
            )
            for row in rows
        ]
    )
