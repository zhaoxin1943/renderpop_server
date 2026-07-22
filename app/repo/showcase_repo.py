import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.showcase import ShowcaseItem


class ShowcaseRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self, *, limit: int = 24) -> list[ShowcaseItem]:
        """Return active showcase items in a shuffled order (fresh each request)."""
        stmt = select(ShowcaseItem).where(
            ShowcaseItem.is_active.is_(True),
            ShowcaseItem.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        random.shuffle(rows)
        return rows[:limit]
