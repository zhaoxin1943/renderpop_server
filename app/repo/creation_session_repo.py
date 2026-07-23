from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.creation_session import CreationSession
from app.models.enums import TaskStatus
from app.models.generation_task import GenerationTask
from app.repo.base import BaseRepo


class CreationSessionRepo(BaseRepo):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def add(self, creation_session: CreationSession) -> CreationSession:
        self.session.add(creation_session)
        await self.session.flush()
        return creation_session

    async def get_owned(
        self,
        session_id: str,
        *,
        user_id: str | None,
        visitor_id: str | None,
    ) -> CreationSession | None:
        stmt = select(CreationSession).where(CreationSession.id == session_id)
        if user_id:
            stmt = stmt.where(CreationSession.user_id == user_id)
        elif visitor_id:
            stmt = stmt.where(CreationSession.visitor_id == visitor_id)
        else:
            return None
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest(
        self,
        *,
        user_id: str | None,
        visitor_id: str | None,
    ) -> CreationSession | None:
        stmt = select(CreationSession)
        if user_id:
            stmt = stmt.where(CreationSession.user_id == user_id)
        elif visitor_id:
            stmt = stmt.where(CreationSession.visitor_id == visitor_id)
        else:
            return None
        stmt = stmt.order_by(CreationSession.updated_at.desc()).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_owned(
        self,
        *,
        user_id: str | None,
        visitor_id: str | None,
    ) -> list[CreationSession]:
        stmt = select(CreationSession)
        if user_id:
            stmt = stmt.where(CreationSession.user_id == user_id)
        elif visitor_id:
            stmt = stmt.where(CreationSession.visitor_id == visitor_id)
        else:
            return []
        stmt = stmt.order_by(CreationSession.updated_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_tasks(self, session_id: str) -> list[GenerationTask]:
        stmt = (
            select(GenerationTask)
            .where(
                GenerationTask.creation_session_id == session_id,
                GenerationTask.status != TaskStatus.CANCELED,
            )
            .order_by(GenerationTask.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

