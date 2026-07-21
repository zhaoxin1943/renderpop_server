from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_usage import DailyUsageCounter
from app.models.base import new_id
from app.repo.base import BaseRepo


class UsageRepo(BaseRepo):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_or_create_for_update(
        self,
        *,
        subject_type: str,
        subject_id: str,
        feature: str,
        usage_date: date,
        limit_snapshot: int,
    ) -> DailyUsageCounter:
        stmt = (
            select(DailyUsageCounter)
            .where(
                DailyUsageCounter.subject_type == subject_type,
                DailyUsageCounter.subject_id == subject_id,
                DailyUsageCounter.feature == feature,
                DailyUsageCounter.usage_date == usage_date,
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return row
        row = DailyUsageCounter(
            id=new_id(),
            subject_type=subject_type,
            subject_id=subject_id,
            feature=feature,
            usage_date=usage_date,
            used_count=0,
            limit_snapshot=limit_snapshot,
        )
        self.session.add(row)
        await self.session.flush()
        # re-lock
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get(
        self,
        *,
        subject_type: str,
        subject_id: str,
        feature: str,
        usage_date: date,
    ) -> DailyUsageCounter | None:
        stmt = select(DailyUsageCounter).where(
            DailyUsageCounter.subject_type == subject_type,
            DailyUsageCounter.subject_id == subject_id,
            DailyUsageCounter.feature == feature,
            DailyUsageCounter.usage_date == usage_date,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
