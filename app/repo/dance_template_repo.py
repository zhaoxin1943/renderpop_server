from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dance_template import DanceTemplate


class DanceTemplateRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active(self) -> list[DanceTemplate]:
        """Return active dance templates sorted by sort_order ascending."""
        stmt = (
            select(DanceTemplate)
            .where(
                DanceTemplate.is_active.is_(True),
                DanceTemplate.deleted_at.is_(None),
            )
            .order_by(DanceTemplate.sort_order.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, template_id: str) -> DanceTemplate | None:
        """Get dance template by ID (active and non-deleted)."""
        stmt = select(DanceTemplate).where(
            DanceTemplate.id == template_id,
            DanceTemplate.is_active.is_(True),
            DanceTemplate.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, template: DanceTemplate) -> DanceTemplate:
        """Add new dance template."""
        self.session.add(template)
        return template
