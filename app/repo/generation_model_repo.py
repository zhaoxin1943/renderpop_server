from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import GenerationModelStatus, ModelModality, TaskType
from app.models.generation_model import GenerationModel
from app.repo.base import BaseRepo


class GenerationModelRepo(BaseRepo):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get(self, model_id: str) -> GenerationModel | None:
        return await self.session.get(GenerationModel, model_id)

    async def get_by_code(self, code: str) -> GenerationModel | None:
        stmt = select(GenerationModel).where(
            GenerationModel.code == code,
            GenerationModel.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_default_for_task_type(self, task_type: TaskType | str) -> GenerationModel | None:
        """
        Resolve default ACTIVE model that lists this task_type.

        Users never pick a model — service always uses this path for video.
        """
        tt = task_type.value if isinstance(task_type, TaskType) else str(task_type)
        stmt = (
            select(GenerationModel)
            .where(
                GenerationModel.status == GenerationModelStatus.ACTIVE,
                GenerationModel.is_default.is_(True),
                GenerationModel.deleted_at.is_(None),
            )
            .order_by(GenerationModel.sort_order.asc())
        )
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        for row in rows:
            types = row.task_types or []
            if tt in types:
                return row
        # fallback: modality VIDEO default without task_types match
        if tt in (TaskType.TEXT_VIDEO.value, TaskType.IMAGE_VIDEO.value):
            for row in rows:
                if row.modality == ModelModality.VIDEO:
                    return row
        return None
