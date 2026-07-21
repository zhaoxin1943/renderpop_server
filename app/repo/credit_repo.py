from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit import (
    CreditGrant,
    CreditReservation,
    CreditReservationItem,
    CreditTransaction,
)
from app.repo.base import BaseRepo


class CreditRepo(BaseRepo):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_grant_by_idempotency(self, key: str) -> CreditGrant | None:
        stmt = select(CreditGrant).where(CreditGrant.idempotency_key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_txn_by_idempotency(self, key: str) -> CreditTransaction | None:
        stmt = select(CreditTransaction).where(CreditTransaction.idempotency_key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active_grants_for_update(self, user_id: str) -> list[CreditGrant]:
        """Lock spendable grants FEFO (earliest expiry first). MySQL: FOR UPDATE."""
        now = datetime.now(UTC)
        stmt = (
            select(CreditGrant)
            .where(
                CreditGrant.user_id == user_id,
                CreditGrant.status == "ACTIVE",
                CreditGrant.available_amount > 0,
            )
            .order_by(
                CreditGrant.expires_at.is_(None),
                CreditGrant.expires_at.asc(),
                CreditGrant.created_at.asc(),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        grants = list(result.scalars().all())
        # Filter expired in Python (timezone-safe)
        live: list[CreditGrant] = []
        for g in grants:
            if g.expires_at is not None and g.expires_at.replace(tzinfo=UTC) <= now:
                continue
            live.append(g)
        return live

    async def sum_balances(self, user_id: str) -> tuple[int, int, int, datetime | None]:
        """Return available, reserved, expiring_soon (7d), next_expiration_at."""
        now = datetime.now(UTC)
        stmt = select(CreditGrant).where(
            CreditGrant.user_id == user_id,
            CreditGrant.status == "ACTIVE",
        )
        result = await self.session.execute(stmt)
        grants = list(result.scalars().all())
        available = 0
        reserved = 0
        expiring_soon = 0
        next_exp: datetime | None = None
        from datetime import timedelta

        soon = now + timedelta(days=7)
        for g in grants:
            exp = g.expires_at
            if exp is not None and exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if exp is not None and exp <= now:
                continue
            available += g.available_amount
            reserved += g.reserved_amount
            if exp is not None:
                if next_exp is None or exp < next_exp:
                    next_exp = exp
                if exp <= soon:
                    expiring_soon += g.available_amount
        return available, reserved, expiring_soon, next_exp

    async def add_grant(self, grant: CreditGrant) -> CreditGrant:
        self.session.add(grant)
        await self.session.flush()
        return grant

    async def add_transaction(self, txn: CreditTransaction) -> CreditTransaction:
        self.session.add(txn)
        await self.session.flush()
        return txn

    async def add_reservation(self, reservation: CreditReservation) -> CreditReservation:
        self.session.add(reservation)
        await self.session.flush()
        return reservation

    async def add_reservation_item(self, item: CreditReservationItem) -> CreditReservationItem:
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_reservation_by_task(self, task_id: str) -> CreditReservation | None:
        stmt = select(CreditReservation).where(CreditReservation.generation_task_id == task_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_reservation(self, reservation_id: str) -> CreditReservation | None:
        return await self.session.get(CreditReservation, reservation_id)

    async def list_reservation_items(self, reservation_id: str) -> list[CreditReservationItem]:
        stmt = select(CreditReservationItem).where(
            CreditReservationItem.reservation_id == reservation_id
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_grant(self, grant_id: str) -> CreditGrant | None:
        return await self.session.get(CreditGrant, grant_id)

    async def list_transactions(
        self, user_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[CreditTransaction]:
        stmt = (
            select(CreditTransaction)
            .where(CreditTransaction.user_id == user_id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
