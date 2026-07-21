from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.showcase import ShowcaseItem


class ShowcaseRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self, *, limit: int = 24) -> list[ShowcaseItem]:
        stmt = (
            select(ShowcaseItem)
            .where(
                ShowcaseItem.is_active.is_(True),
                ShowcaseItem.deleted_at.is_(None),
            )
            .order_by(ShowcaseItem.sort_order.asc(), ShowcaseItem.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
