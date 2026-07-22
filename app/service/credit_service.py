"""Credit ledger: one-shot grants, FEFO reserve/capture/release."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.commerce import (
    CREDIT_PACK_EXPIRE_DAYS,
    RESERVATION_TTL_HOURS,
    SIGNUP_BONUS_CREDITS,
    SIGNUP_BONUS_DAYS,
    SUBSCRIPTION_CARRY_MULTIPLIER,
    SUBSCRIPTION_CREDIT_EXTRA_PERIOD_DAYS,
    SUBSCRIPTION_CREDITS,
)
from app.core.errors import InsufficientCredits
from app.models.base import new_id
from app.models.credit import (
    CreditGrant,
    CreditReservation,
    CreditReservationItem,
    CreditTransaction,
)
from app.models.enums import (
    CreditGrantStatus,
    CreditGrantType,
    CreditReservationStatus,
    CreditSourceType,
    CreditTxnType,
    MembershipPlan,
)
from app.repo.credit_repo import CreditRepo
from app.schemas.credit import CreditBalanceResponse, CreditTransactionResponse


class CreditService:
    def __init__(self, repo: CreditRepo) -> None:
        self._repo = repo

    async def get_balance(self, user_id: str) -> CreditBalanceResponse:
        available, reserved, expiring_soon, next_exp = await self._repo.sum_balances(user_id)
        return CreditBalanceResponse(
            available=available,
            reserved=reserved,
            expiring_soon=expiring_soon,
            next_expiration_at=next_exp,
        )

    async def grant_signup_bonus(self, user_id: str) -> CreditGrant | None:
        key = f"signup_bonus:{user_id}"
        existing = await self._repo.get_grant_by_idempotency(key)
        if existing:
            return existing
        expires = datetime.now(UTC) + timedelta(days=SIGNUP_BONUS_DAYS)
        return await self._grant(
            user_id=user_id,
            grant_type=CreditGrantType.SIGNUP_BONUS,
            amount=SIGNUP_BONUS_CREDITS,
            expires_at=expires,
            source_type=CreditSourceType.SIGNUP,
            source_id=user_id,
            idempotency_key=key,
            metadata={"reason": "signup_bonus"},
        )

    async def grant_purchased_pack(
        self,
        *,
        user_id: str,
        amount: int,
        order_id: str,
        payment_id: str,
        product_code: str,
    ) -> CreditGrant:
        key = f"credit_pack:{payment_id}"
        existing = await self._repo.get_grant_by_idempotency(key)
        if existing:
            return existing
        expires = datetime.now(UTC) + timedelta(days=CREDIT_PACK_EXPIRE_DAYS)
        return await self._grant(
            user_id=user_id,
            grant_type=CreditGrantType.PURCHASED,
            amount=amount,
            expires_at=expires,
            source_type=CreditSourceType.ORDER,
            source_id=order_id,
            idempotency_key=key,
            metadata={"product_code": product_code, "payment_id": payment_id},
        )

    async def grant_compensation(
        self,
        *,
        user_id: str,
        amount: int,
        reason: str = "compensation",
        expires_days: int = 90,
        idempotency_key: str | None = None,
    ) -> CreditGrant:
        """Manual / admin / dev compensation credits."""
        key = idempotency_key or f"compensation:{user_id}:{new_id()}"
        existing = await self._repo.get_grant_by_idempotency(key)
        if existing:
            return existing
        return await self._grant(
            user_id=user_id,
            grant_type=CreditGrantType.COMPENSATION,
            amount=amount,
            expires_at=datetime.now(UTC) + timedelta(days=expires_days),
            source_type=CreditSourceType.ADMIN,
            source_id=new_id(),
            idempotency_key=key,
            metadata={"reason": reason},
        )

    async def grant_subscription_period(
        self,
        *,
        user_id: str,
        plan_code: MembershipPlan | str,
        provider_subscription_id: str,
        period_start: datetime,
        period_end: datetime | None = None,
    ) -> CreditGrant | None:
        """
        One-shot monthly membership credits with 2× carry cap.

        Idempotency: subscription_credit:{sub_id}:{period_start_iso}
        """
        period_key = period_start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        key = f"subscription_credit:{provider_subscription_id}:{period_key}"
        existing = await self._repo.get_grant_by_idempotency(key)
        if existing:
            return existing

        try:
            membership_plan = MembershipPlan(plan_code)
        except ValueError:
            return None

        full = SUBSCRIPTION_CREDITS.get(membership_plan, 0)
        if full <= 0:
            return None

        # Carry cap: available+reserved of existing SUBSCRIPTION grants
        # Cap applies to membership credits remaining vs 2× this period grant
        sub_remaining = await self._subscription_remaining(user_id)
        cap = full * SUBSCRIPTION_CARRY_MULTIPLIER
        room = max(0, cap - sub_remaining)
        amount = min(full, room)
        if amount <= 0:
            # Still record a zero? Skip grant but idempotency row needed to block retries.
            # Create exhausted zero-grant for idempotency.
            amount = 0

        if period_end is None:
            expires = datetime.now(UTC) + timedelta(days=SUBSCRIPTION_CREDIT_EXTRA_PERIOD_DAYS * 2)
        else:
            expires = period_end.astimezone(UTC) + timedelta(
                days=SUBSCRIPTION_CREDIT_EXTRA_PERIOD_DAYS
            )

        if amount == 0:
            grant = CreditGrant(
                id=new_id(),
                user_id=user_id,
                grant_type=CreditGrantType.SUBSCRIPTION,
                original_amount=0,
                available_amount=0,
                reserved_amount=0,
                consumed_amount=0,
                revoked_amount=0,
                expires_at=expires,
                source_type=CreditSourceType.SUBSCRIPTION_PERIOD,
                source_id=provider_subscription_id,
                idempotency_key=key,
                status=CreditGrantStatus.EXHAUSTED,
            )
            await self._repo.add_grant(grant)
            return grant

        return await self._grant(
            user_id=user_id,
            grant_type=CreditGrantType.SUBSCRIPTION,
            amount=amount,
            expires_at=expires,
            source_type=CreditSourceType.SUBSCRIPTION_PERIOD,
            source_id=provider_subscription_id,
            idempotency_key=key,
            metadata={
                "plan_code": membership_plan.value,
                "full_amount": full,
                "capped_amount": amount,
                "period_start": period_key,
            },
        )

    async def _subscription_remaining(self, user_id: str) -> int:
        from sqlalchemy import select

        from app.models.credit import CreditGrant as CG

        now = datetime.now(UTC)
        stmt = select(CG).where(
            CG.user_id == user_id,
            CG.grant_type == CreditGrantType.SUBSCRIPTION,
            CG.status == CreditGrantStatus.ACTIVE,
        )
        result = await self._repo.session.execute(stmt)
        total = 0
        for g in result.scalars().all():
            exp = g.expires_at
            if exp is not None and exp.replace(tzinfo=UTC) <= now:
                continue
            total += g.available_amount + g.reserved_amount
        return total

    async def _grant(
        self,
        *,
        user_id: str,
        grant_type: CreditGrantType,
        amount: int,
        expires_at: datetime | None,
        source_type: CreditSourceType,
        source_id: str | None,
        idempotency_key: str,
        metadata: dict | None = None,
    ) -> CreditGrant:
        grant = CreditGrant(
            id=new_id(),
            user_id=user_id,
            grant_type=grant_type,
            original_amount=amount,
            available_amount=amount,
            reserved_amount=0,
            consumed_amount=0,
            revoked_amount=0,
            expires_at=expires_at,
            source_type=source_type,
            source_id=source_id,
            idempotency_key=idempotency_key,
            status=CreditGrantStatus.ACTIVE if amount > 0 else CreditGrantStatus.EXHAUSTED,
        )
        await self._repo.add_grant(grant)
        if amount > 0:
            await self._repo.add_transaction(
                CreditTransaction(
                    id=new_id(),
                    user_id=user_id,
                    grant_id=grant.id,
                    type=CreditTxnType.GRANT,
                    amount=amount,
                    balance_after={
                        "available": grant.available_amount,
                        "reserved": grant.reserved_amount,
                        "consumed": grant.consumed_amount,
                    },
                    idempotency_key=f"txn:grant:{idempotency_key}",
                    metadata_json=metadata,
                )
            )
        return grant

    async def reserve_for_task(
        self,
        *,
        user_id: str,
        task_id: str,
        amount: int,
        pricing_snapshot: dict | None = None,
    ) -> CreditReservation:
        """FEFO reserve. Raises InsufficientCredits if not enough."""
        existing = await self._repo.get_reservation_by_task(task_id)
        if existing:
            return existing

        if amount <= 0:
            raise ValueError("reserve amount must be positive")

        grants = await self._repo.list_active_grants_for_update(user_id)
        plan: list[tuple[CreditGrant, int]] = []
        remaining = amount
        for g in grants:
            if remaining <= 0:
                break
            take = min(g.available_amount, remaining)
            if take <= 0:
                continue
            plan.append((g, take))
            remaining -= take

        if remaining > 0:
            raise InsufficientCredits(
                f"Need {amount} credits, short by {remaining}"
            )

        reservation = CreditReservation(
            id=new_id(),
            user_id=user_id,
            generation_task_id=task_id,
            total_amount=amount,
            status=CreditReservationStatus.ACTIVE,
            expires_at=datetime.now(UTC) + timedelta(hours=RESERVATION_TTL_HOURS),
            pricing_snapshot=pricing_snapshot,
        )
        await self._repo.add_reservation(reservation)

        for g, take in plan:
            g.available_amount -= take
            g.reserved_amount += take
            if g.available_amount == 0 and g.reserved_amount == 0:
                g.status = CreditGrantStatus.EXHAUSTED
            await self._repo.add_reservation_item(
                CreditReservationItem(
                    id=new_id(),
                    reservation_id=reservation.id,
                    grant_id=g.id,
                    amount=take,
                )
            )
            await self._repo.add_transaction(
                CreditTransaction(
                    id=new_id(),
                    user_id=user_id,
                    grant_id=g.id,
                    generation_task_id=task_id,
                    type=CreditTxnType.RESERVE,
                    amount=take,
                    balance_after={
                        "available": g.available_amount,
                        "reserved": g.reserved_amount,
                        "consumed": g.consumed_amount,
                    },
                    idempotency_key=f"txn:reserve:{task_id}:{g.id}",
                    metadata_json={"reservation_id": reservation.id},
                )
            )
        await self._repo.session.flush()
        return reservation

    async def capture_reservation(self, *, task_id: str) -> CreditReservation | None:
        reservation = await self._repo.get_reservation_by_task(task_id)
        if reservation is None:
            return None
        if reservation.status == CreditReservationStatus.CAPTURED:
            return reservation
        if reservation.status != CreditReservationStatus.ACTIVE:
            return reservation

        items = await self._repo.list_reservation_items(reservation.id)
        for item in items:
            grant = await self._repo.get_grant(item.grant_id)
            if grant is None:
                continue
            take = item.amount
            grant.reserved_amount = max(0, grant.reserved_amount - take)
            grant.consumed_amount += take
            if grant.available_amount == 0 and grant.reserved_amount == 0:
                grant.status = CreditGrantStatus.EXHAUSTED
            await self._repo.add_transaction(
                CreditTransaction(
                    id=new_id(),
                    user_id=reservation.user_id,
                    grant_id=grant.id,
                    generation_task_id=task_id,
                    type=CreditTxnType.CAPTURE,
                    amount=take,
                    balance_after={
                        "available": grant.available_amount,
                        "reserved": grant.reserved_amount,
                        "consumed": grant.consumed_amount,
                    },
                    idempotency_key=f"txn:capture:{task_id}:{grant.id}",
                    metadata_json={"reservation_id": reservation.id},
                )
            )
        reservation.status = CreditReservationStatus.CAPTURED
        await self._repo.session.flush()
        return reservation

    async def release_reservation(self, *, task_id: str) -> CreditReservation | None:
        reservation = await self._repo.get_reservation_by_task(task_id)
        if reservation is None:
            return None
        if reservation.status == CreditReservationStatus.RELEASED:
            return reservation
        if reservation.status != CreditReservationStatus.ACTIVE:
            return reservation

        items = await self._repo.list_reservation_items(reservation.id)
        now = datetime.now(UTC)
        for item in items:
            grant = await self._repo.get_grant(item.grant_id)
            if grant is None:
                continue
            take = item.amount
            grant.reserved_amount = max(0, grant.reserved_amount - take)
            # If grant expired during hold, still restore available then mark expired if past
            grant.available_amount += take
            exp = grant.expires_at
            if exp is not None and exp.replace(tzinfo=UTC) <= now:
                # Move restored amount to expired via EXPIRE txn path: keep simple — mark EXPIRED
                # and zero available for expired portion
                expired_amt = grant.available_amount
                grant.available_amount = 0
                grant.status = CreditGrantStatus.EXPIRED
                await self._repo.add_transaction(
                    CreditTransaction(
                        id=new_id(),
                        user_id=reservation.user_id,
                        grant_id=grant.id,
                        generation_task_id=task_id,
                        type=CreditTxnType.RELEASE,
                        amount=take,
                        balance_after={
                            "available": 0,
                            "reserved": grant.reserved_amount,
                            "consumed": grant.consumed_amount,
                        },
                        idempotency_key=f"txn:release:{task_id}:{grant.id}",
                        metadata_json={
                            "reservation_id": reservation.id,
                            "expired_on_release": True,
                            "expired_amount": expired_amt,
                        },
                    )
                )
            else:
                if grant.status == CreditGrantStatus.EXHAUSTED:
                    grant.status = CreditGrantStatus.ACTIVE
                await self._repo.add_transaction(
                    CreditTransaction(
                        id=new_id(),
                        user_id=reservation.user_id,
                        grant_id=grant.id,
                        generation_task_id=task_id,
                        type=CreditTxnType.RELEASE,
                        amount=take,
                        balance_after={
                            "available": grant.available_amount,
                            "reserved": grant.reserved_amount,
                            "consumed": grant.consumed_amount,
                        },
                        idempotency_key=f"txn:release:{task_id}:{grant.id}",
                        metadata_json={"reservation_id": reservation.id},
                    )
                )
        reservation.status = CreditReservationStatus.RELEASED
        await self._repo.session.flush()
        return reservation

    async def list_transactions(
        self, user_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[CreditTransactionResponse]:
        rows = await self._repo.list_transactions(user_id, limit=limit, offset=offset)
        out: list[CreditTransactionResponse] = []
        for t in rows:
            # User-facing: CAPTURE = spend; RESERVE = hold; RELEASE = refund hold
            if t.type == CreditTxnType.RESERVE:
                amount = -t.amount
            elif t.type in (
                CreditTxnType.CAPTURE,
                CreditTxnType.EXPIRE,
                CreditTxnType.REVOKE,
            ):
                amount = -t.amount
            else:
                amount = t.amount
            out.append(
                CreditTransactionResponse(
                    id=t.id,
                    type=t.type,
                    amount=amount,
                    generation_task_id=t.generation_task_id,
                    created_at=t.created_at,
                    metadata=t.metadata_json,
                )
            )
        return out
