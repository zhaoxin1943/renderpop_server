"""Development-only helpers (create user, grant credits)."""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import NotFound
from app.models.base import new_id
from app.models.enums import RiskLevel, UserStatus
from app.models.user import User
from app.repo.user_repo import UserRepo
from app.schemas.dev import DevUserResponse, GrantCreditsResponse
from app.service.credit_service import CreditService


class DevService:
    def __init__(
        self,
        users: UserRepo,
        credits: CreditService,
        settings: Settings,
    ) -> None:
        self._users = users
        self._credits = credits
        self._settings = settings

    def _require_development(self) -> None:
        if not self._settings.is_development:
            raise NotFound("Not found")

    async def create_user(
        self,
        *,
        email: str,
        display_name: str | None = None,
    ) -> DevUserResponse:
        self._require_development()
        normalized = email.lower()
        existing = await self._users.get_by_email(normalized)
        if existing:
            return DevUserResponse(id=existing.id, email=existing.email, created=False)
        user = User(
            id=new_id(),
            email=normalized,
            display_name=display_name,
            status=UserStatus.ACTIVE,
            risk_level=RiskLevel.LOW,
        )
        await self._users.create(user)
        return DevUserResponse(id=user.id, email=user.email, created=True)

    async def grant_credits(
        self,
        *,
        user_id: str,
        amount: int,
        reason: str = "dev_grant",
    ) -> GrantCreditsResponse:
        self._require_development()
        grant = await self._credits.grant_compensation(
            user_id=user_id,
            amount=amount,
            reason=reason,
            idempotency_key=f"dev_grant:{user_id}:{new_id()}",
        )
        balance = await self._credits.get_balance(user_id)
        return GrantCreditsResponse(grant_id=grant.id, balance=balance)
