from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generation_task import GenerationAttempt, GenerationTask
from app.repo.base import BaseRepo

ACTIVE_STATUSES = (
    "CREATED",
    "MODERATING",
    "QUEUED",
    "SUBMITTING",
    "PROCESSING",
    "CANCEL_REQUESTED",
)


class GenerationRepo(BaseRepo):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get(self, task_id: str) -> GenerationTask | None:
        return await self.session.get(GenerationTask, task_id)

    async def get_by_idempotency(self, key: str) -> GenerationTask | None:
        stmt = select(GenerationTask).where(GenerationTask.idempotency_key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_provider_task_id(self, provider_task_id: str) -> GenerationTask | None:
        stmt = select(GenerationTask).where(GenerationTask.provider_task_id == provider_task_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, task: GenerationTask) -> GenerationTask:
        self.session.add(task)
        await self.session.flush()
        return task

    async def add_attempt(self, attempt: GenerationAttempt) -> GenerationAttempt:
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def count_active_for_user(self, user_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(GenerationTask)
            .where(
                GenerationTask.user_id == user_id,
                GenerationTask.status.in_(ACTIVE_STATUSES),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def count_active_for_visitor(self, visitor_id: str) -> int:
        stmt = (
            select(func.count())
            .select_from(GenerationTask)
            .where(
                GenerationTask.visitor_id == visitor_id,
                GenerationTask.status.in_(ACTIVE_STATUSES),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def list_for_user(
        self,
        user_id: str,
        *,
        task_type: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[GenerationTask]:
        stmt = select(GenerationTask).where(GenerationTask.user_id == user_id)
        if task_type:
            stmt = stmt.where(GenerationTask.task_type == task_type)
        if status:
            stmt = stmt.where(GenerationTask.status == status)
        stmt = stmt.order_by(GenerationTask.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
