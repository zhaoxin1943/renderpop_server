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

    async def list_active_defaults(self) -> list[GenerationModel]:
        """All ACTIVE default catalog rows (image + video), ordered for UI."""
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
        return list(result.scalars().all())

    async def map_default_by_task_type(self) -> dict[str, GenerationModel]:
        """
        task_type value -> first default ACTIVE model that lists it.

        One model may cover multiple task_types (e.g. Pollo video).
        """
        rows = await self.list_active_defaults()
        out: dict[str, GenerationModel] = {}
        for row in rows:
            for tt in row.task_types or []:
                if tt not in out:
                    out[str(tt)] = row
        return out

    async def get_default_for_task_type(self, task_type: TaskType | str) -> GenerationModel | None:
        """
        Resolve default ACTIVE model that lists this task_type.

        Users never pick a model — service routes by job_type.
        """
        tt = task_type.value if isinstance(task_type, TaskType) else str(task_type)
        mapping = await self.map_default_by_task_type()
        if tt in mapping:
            return mapping[tt]
        # fallback: modality VIDEO default without task_types match (Pollo only)
        if tt in (TaskType.TEXT_VIDEO.value, TaskType.IMAGE_VIDEO.value):
            for row in await self.list_active_defaults():
                if (
                    row.modality == ModelModality.VIDEO
                    and TaskType.DANCE_VIDEO.value not in (row.task_types or [])
                ):
                    return row
        return None
