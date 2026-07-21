from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PaymentProvider
from app.models.order import Order
from app.models.payment_event import PaymentEvent
from app.repo.base import BaseRepo


class OrderRepo(BaseRepo):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get(self, order_id: str) -> Order | None:
        return await self.session.get(Order, order_id)

    async def get_by_idempotency(self, user_id: str, key: str) -> Order | None:
        stmt = select(Order).where(Order.user_id == user_id, Order.idempotency_key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, order: Order) -> Order:
        self.session.add(order)
        await self.session.flush()
        return order

    async def get_event(
        self, provider: PaymentProvider | str, event_id: str
    ) -> PaymentEvent | None:
        stmt = select(PaymentEvent).where(
            PaymentEvent.provider == provider,
            PaymentEvent.event_id == event_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_event(self, event: PaymentEvent) -> PaymentEvent:
        self.session.add(event)
        await self.session.flush()
        return event
