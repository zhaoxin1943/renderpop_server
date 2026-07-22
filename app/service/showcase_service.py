"""Public showcase listing (homepage waterfall)."""

from __future__ import annotations

from app.repo.showcase_repo import ShowcaseRepo
from app.schemas.showcase import ShowcaseItemResponse, ShowcaseListResponse


class ShowcaseService:
    def __init__(self, repo: ShowcaseRepo) -> None:
        self._repo = repo

    async def list_active(self, *, limit: int = 24) -> ShowcaseListResponse:
        rows = await self._repo.list_active(limit=limit)
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
