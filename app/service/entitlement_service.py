"""Membership + Fast quota resolution."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.core.commerce import (
    CONCURRENT_JOB_LIMITS,
    FAST_DAILY_LIMITS,
    MEMBERSHIP_GRACE_DAYS,
    PLAN_CREATOR,
    PLAN_FREE,
    PLAN_PRO,
    PLAN_VISITOR,
)
from app.models.enums import (
    MembershipPlan,
    PlanCode,
    SubscriptionStatus,
    UsageFeature,
    UsageSubjectType,
)
from app.models.subscription import Subscription
from app.repo.subscription_repo import SubscriptionRepo
from app.repo.usage_repo import UsageRepo
from app.schemas.credit import CreditBalanceResponse
from app.schemas.me import EntitlementsResponse, FastImageQuotaResponse
from app.service.credit_service import CreditService

_INACTIVE_SUB_STATUSES = frozenset(
    {
        SubscriptionStatus.FAILED,
        SubscriptionStatus.EXPIRED,
        SubscriptionStatus.INCOMPLETE,
    }
)
_PERIOD_ACTIVE_STATUSES = frozenset(
    {SubscriptionStatus.ACTIVE, SubscriptionStatus.CANCELED}
)


class EntitlementService:
    def __init__(
        self,
        subscription_repo: SubscriptionRepo,
        usage_repo: UsageRepo,
        credit_service: CreditService,
    ) -> None:
        self._subs = subscription_repo
        self._usage = usage_repo
        self._credits = credit_service

    def _is_membership_active(self, sub: Subscription, now: datetime) -> bool:
        if sub.status in _INACTIVE_SUB_STATUSES:
            return False
        if sub.current_period_end is None:
            return sub.status == SubscriptionStatus.ACTIVE
        end = sub.current_period_end
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        grace = timedelta(days=MEMBERSHIP_GRACE_DAYS)
        # ACTIVE or CANCELED still in period; ON_HOLD within period+grace
        if sub.status in _PERIOD_ACTIVE_STATUSES and now < end:
            return True
        if sub.status == SubscriptionStatus.ON_HOLD and now < end + grace:
            return True
        return False

    async def resolve_plan(self, user_id: str | None) -> PlanCode:
        if not user_id:
            return PLAN_FREE
        subs = await self._subs.list_for_user(user_id)
        now = datetime.now(UTC)
        best = PLAN_FREE
        rank = {PLAN_FREE: 0, PLAN_CREATOR: 1, PLAN_PRO: 2}
        for s in subs:
            if not self._is_membership_active(s, now):
                continue
            plan = PlanCode(s.plan_code) if s.plan_code else PLAN_FREE
            if rank.get(plan, 0) > rank.get(best, 0):
                best = plan
        return best

    async def get_entitlements(
        self, user_id: str | None, visitor_id: str | None = None
    ) -> EntitlementsResponse:
        plan = await self.resolve_plan(user_id) if user_id else PLAN_FREE
        if not user_id:
            plan_key = PLAN_VISITOR
            daily_limit = FAST_DAILY_LIMITS[PLAN_VISITOR]
        else:
            plan_key = plan
            daily_limit = FAST_DAILY_LIMITS.get(plan, FAST_DAILY_LIMITS[PLAN_FREE])

        today = datetime.now(UTC).date()
        used = 0
        if user_id:
            row = await self._usage.get(
                subject_type=UsageSubjectType.USER,
                subject_id=user_id,
                feature=UsageFeature.FAST_IMAGE,
                usage_date=today,
            )
            used = row.used_count if row else 0
        elif visitor_id:
            row = await self._usage.get(
                subject_type=UsageSubjectType.VISITOR,
                subject_id=visitor_id,
                feature=UsageFeature.FAST_IMAGE,
                usage_date=today,
            )
            used = row.used_count if row else 0

        credits = (
            await self._credits.get_balance(user_id)
            if user_id
            else CreditBalanceResponse(
                available=0, reserved=0, expiring_soon=0, next_expiration_at=None
            )
        )

        membership_active = plan in (PLAN_CREATOR, PLAN_PRO)
        period_end = None
        if user_id and membership_active:
            subs = await self._subs.list_for_user(user_id)
            now = datetime.now(UTC)
            membership_plan = MembershipPlan(plan)
            for s in subs:
                if self._is_membership_active(s, now) and s.plan_code == membership_plan:
                    period_end = s.current_period_end
                    break

        resets = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=UTC)

        return EntitlementsResponse(
            plan=plan if user_id else PLAN_VISITOR,
            membership_active=membership_active,
            current_period_end=period_end,
            fast_image=FastImageQuotaResponse(
                daily_limit=daily_limit,
                used=used,
                remaining=max(0, daily_limit - used),
                resets_at=resets,
            ),
            credits=credits,
            concurrent_job_limit=CONCURRENT_JOB_LIMITS.get(
                plan_key if user_id else PLAN_VISITOR, 1
            ),
        )

    async def consume_fast_quota(
        self,
        *,
        user_id: str | None,
        visitor_id: str | None,
    ) -> tuple[int, int]:
        """Atomically consume 1 Fast slot. Returns (used, limit). Raises DailyLimitReached."""
        from app.core.errors import DailyLimitReached

        plan = await self.resolve_plan(user_id) if user_id else PLAN_FREE
        if user_id:
            subject_type, subject_id = UsageSubjectType.USER, user_id
            limit = FAST_DAILY_LIMITS.get(plan, FAST_DAILY_LIMITS[PLAN_FREE])
        else:
            if not visitor_id:
                raise DailyLimitReached("Visitor id required")
            subject_type, subject_id = UsageSubjectType.VISITOR, visitor_id
            limit = FAST_DAILY_LIMITS[PLAN_VISITOR]

        today = date.today()  # server local; prefer UTC date
        today = datetime.now(UTC).date()
        row = await self._usage.get_or_create_for_update(
            subject_type=subject_type,
            subject_id=subject_id,
            feature=UsageFeature.FAST_IMAGE,
            usage_date=today,
            limit_snapshot=limit,
        )
        # Refresh limit snapshot for membership changes
        row.limit_snapshot = limit
        if row.used_count >= limit:
            raise DailyLimitReached()
        row.used_count += 1
        await self._usage.session.flush()
        return row.used_count, limit

    async def refund_fast_quota(
        self,
        *,
        user_id: str | None,
        visitor_id: str | None,
    ) -> None:
        today = datetime.now(UTC).date()
        if user_id:
            subject_type, subject_id = UsageSubjectType.USER, user_id
        elif visitor_id:
            subject_type, subject_id = UsageSubjectType.VISITOR, visitor_id
        else:
            return
        row = await self._usage.get(
            subject_type=subject_type,
            subject_id=subject_id,
            feature=UsageFeature.FAST_IMAGE,
            usage_date=today,
        )
        if row and row.used_count > 0:
            row.used_count -= 1
            await self._usage.session.flush()
