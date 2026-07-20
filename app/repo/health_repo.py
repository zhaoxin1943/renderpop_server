from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repo.base import BaseRepo


class HealthRepo(BaseRepo):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def ping_database(self) -> bool:
        result = await self.session.execute(text("SELECT 1"))
        return result.scalar_one() == 1
