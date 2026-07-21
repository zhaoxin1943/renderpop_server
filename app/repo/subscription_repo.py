from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription
from app.repo.base import BaseRepo


class SubscriptionRepo(BaseRepo):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_provider_id(self, provider: str, provider_sub_id: str) -> Subscription | None:
        stmt = select(Subscription).where(
            Subscription.provider == provider,
            Subscription.provider_subscription_id == provider_sub_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str) -> list[Subscription]:
        stmt = (
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, sub: Subscription) -> Subscription:
        self.session.add(sub)
        await self.session.flush()
        return sub
