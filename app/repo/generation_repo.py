from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TaskStatus, TaskType
from app.models.generation_task import GenerationAttempt, GenerationTask
from app.repo.base import BaseRepo


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
                GenerationTask.status.in_(TaskStatus.active()),
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
                GenerationTask.status.in_(TaskStatus.active()),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def list_for_user(
        self,
        user_id: str,
        *,
        task_type: TaskType | str | None = None,
        task_types: list[TaskType] | None = None,
        status: TaskStatus | str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[GenerationTask]:
        stmt = select(GenerationTask).where(GenerationTask.user_id == user_id)
        if task_type:
            stmt = stmt.where(GenerationTask.task_type == task_type)
        if task_types:
            stmt = stmt.where(GenerationTask.task_type.in_(task_types))
        if status:
            stmt = stmt.where(GenerationTask.status == status)
        stmt = stmt.order_by(GenerationTask.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete(self, task: GenerationTask) -> None:
        await self.session.delete(task)
        await self.session.flush()

    async def count_active_by_provider(self, provider: GenerationProvider) -> int:
        """Count tasks currently occupying provider slots (PROCESSING or SUBMITTING)."""
        stmt = (
            select(func.count())
            .select_from(GenerationTask)
            .where(
                GenerationTask.provider == provider,
                GenerationTask.status.in_({TaskStatus.PROCESSING, TaskStatus.SUBMITTING}),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def fetch_next_queued_tasks(
        self, provider: GenerationProvider, limit: int
    ) -> list[GenerationTask]:
        """Fetch next QUEUED tasks for provider sorted by priority DESC, created_at ASC."""
        if limit <= 0:
            return []
        stmt = (
            select(GenerationTask)
            .where(
                GenerationTask.provider == provider,
                GenerationTask.status == TaskStatus.QUEUED,
            )
            .order_by(GenerationTask.priority.desc(), GenerationTask.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def fetch_all_queued_tasks_by_provider(
        self, provider: GenerationProvider
    ) -> list[GenerationTask]:
        """Fetch all QUEUED tasks for a specific provider sorted by priority DESC, created_at ASC."""
        stmt = (
            select(GenerationTask)
            .where(
                GenerationTask.provider == provider,
                GenerationTask.status == TaskStatus.QUEUED,
            )
            .order_by(GenerationTask.priority.desc(), GenerationTask.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_queued_ahead(
        self,
        *,
        task_id: str,
        provider: GenerationProvider | None,
        priority: int,
        created_at: Any,
    ) -> int:
        """Count QUEUED tasks ahead of this task in priority order."""
        from sqlalchemy import or_

        stmt = select(func.count()).select_from(GenerationTask).where(
            GenerationTask.status == TaskStatus.QUEUED,
            GenerationTask.id != task_id,
        )
        if provider:
            stmt = stmt.where(GenerationTask.provider == provider)
        stmt = stmt.where(
            or_(
                GenerationTask.priority > priority,
                (GenerationTask.priority == priority) & (GenerationTask.created_at < created_at),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    async def fetch_expired_queued_tasks(self, cutoff_time: Any) -> list[GenerationTask]:
        """Fetch QUEUED tasks created before cutoff_time (e.g. 20 minutes ago)."""
        stmt = (
            select(GenerationTask)
            .where(
                GenerationTask.status == TaskStatus.QUEUED,
                GenerationTask.created_at < cutoff_time,
            )
            .order_by(GenerationTask.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


