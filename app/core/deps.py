"""
FastAPI dependency injection wiring.

Layer: api -> service -> repo; one AsyncSession per request.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.providers.dodo import DodoClient
from app.providers.pollo import PolloClient
from app.providers.runninghub import RunningHubClient
from app.providers.s3 import S3Storage
from app.repo.base import BaseRepo
from app.repo.creation_session_repo import CreationSessionRepo
from app.repo.credit_repo import CreditRepo
from app.repo.generation_model_repo import GenerationModelRepo
from app.repo.generation_repo import GenerationRepo
from app.repo.health_repo import HealthRepo
from app.repo.order_repo import OrderRepo
from app.repo.product_repo import ProductRepo
from app.repo.showcase_repo import ShowcaseRepo
from app.repo.subscription_repo import SubscriptionRepo
from app.repo.usage_repo import UsageRepo
from app.repo.user_repo import UserRepo
from app.service.asset_service import AssetService
from app.service.auth_service import SESSION_COOKIE_NAME, AuthService
from app.service.billing_service import BillingService
from app.service.creation_session_service import CreationSessionService
from app.service.credit_service import CreditService
from app.service.dev_service import DevService
from app.service.entitlement_service import EntitlementService
from app.service.generation_service import GenerationService
from app.service.health_service import HealthService
from app.service.showcase_service import ShowcaseService

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_session(session: SessionDep) -> AsyncGenerator[AsyncSession, None]:
    yield session


# --- repos ---


def get_health_repo(session: SessionDep) -> HealthRepo:
    return HealthRepo(session)


def get_user_repo(session: SessionDep) -> UserRepo:
    return UserRepo(session)


def get_credit_repo(session: SessionDep) -> CreditRepo:
    return CreditRepo(session)


def get_creation_session_repo(session: SessionDep) -> CreationSessionRepo:
    return CreationSessionRepo(session)


def get_product_repo(session: SessionDep) -> ProductRepo:
    return ProductRepo(session)


def get_order_repo(session: SessionDep) -> OrderRepo:
    return OrderRepo(session)


def get_subscription_repo(session: SessionDep) -> SubscriptionRepo:
    return SubscriptionRepo(session)


def get_generation_repo(session: SessionDep) -> GenerationRepo:
    return GenerationRepo(session)


def get_generation_model_repo(session: SessionDep) -> GenerationModelRepo:
    return GenerationModelRepo(session)


def get_usage_repo(session: SessionDep) -> UsageRepo:
    return UsageRepo(session)


def get_showcase_repo(session: SessionDep) -> ShowcaseRepo:
    return ShowcaseRepo(session)


HealthRepoDep = Annotated[HealthRepo, Depends(get_health_repo)]
UserRepoDep = Annotated[UserRepo, Depends(get_user_repo)]
CreditRepoDep = Annotated[CreditRepo, Depends(get_credit_repo)]
CreationSessionRepoDep = Annotated[CreationSessionRepo, Depends(get_creation_session_repo)]
ProductRepoDep = Annotated[ProductRepo, Depends(get_product_repo)]
OrderRepoDep = Annotated[OrderRepo, Depends(get_order_repo)]
SubscriptionRepoDep = Annotated[SubscriptionRepo, Depends(get_subscription_repo)]
GenerationRepoDep = Annotated[GenerationRepo, Depends(get_generation_repo)]
GenerationModelRepoDep = Annotated[GenerationModelRepo, Depends(get_generation_model_repo)]
UsageRepoDep = Annotated[UsageRepo, Depends(get_usage_repo)]
ShowcaseRepoDep = Annotated[ShowcaseRepo, Depends(get_showcase_repo)]


# --- services ---


def get_health_service(repo: HealthRepoDep) -> HealthService:
    return HealthService(repo)


def get_credit_service(repo: CreditRepoDep) -> CreditService:
    return CreditService(repo)


def get_creation_session_service(
    repo: CreationSessionRepoDep,
) -> CreationSessionService:
    return CreationSessionService(repo)


def get_entitlement_service(
    subs: SubscriptionRepoDep,
    usage: UsageRepoDep,
    credits: Annotated[CreditService, Depends(get_credit_service)],
) -> EntitlementService:
    return EntitlementService(subs, usage, credits)


def get_s3_storage(settings: SettingsDep) -> S3Storage:
    return S3Storage(settings)


def get_generation_service(
    gen_repo: GenerationRepoDep,
    model_repo: GenerationModelRepoDep,
    credits: Annotated[CreditService, Depends(get_credit_service)],
    entitlements: Annotated[EntitlementService, Depends(get_entitlement_service)],
    settings: SettingsDep,
    s3: Annotated[S3Storage, Depends(get_s3_storage)],
) -> GenerationService:
    return GenerationService(
        gen_repo,
        credits,
        entitlements,
        settings,
        rh=RunningHubClient(settings),
        pollo=PolloClient(settings),
        s3=s3,
        model_repo=model_repo,
    )


def get_asset_service(
    session: SessionDep,
    s3: Annotated[S3Storage, Depends(get_s3_storage)],
) -> AssetService:
    return AssetService(BaseRepo(session), s3)


def get_billing_service(
    products: ProductRepoDep,
    orders: OrderRepoDep,
    subs: SubscriptionRepoDep,
    credits: Annotated[CreditService, Depends(get_credit_service)],
    settings: SettingsDep,
) -> BillingService:
    return BillingService(
        products,
        orders,
        subs,
        credits,
        settings,
        dodo=DodoClient(settings),
    )


def get_auth_service(users: UserRepoDep, settings: SettingsDep) -> AuthService:
    return AuthService(users, settings)


def get_showcase_service(repo: ShowcaseRepoDep) -> ShowcaseService:
    return ShowcaseService(repo)


def get_dev_service(
    users: UserRepoDep,
    credits: Annotated[CreditService, Depends(get_credit_service)],
    settings: SettingsDep,
) -> DevService:
    return DevService(users, credits, settings)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
CreditServiceDep = Annotated[CreditService, Depends(get_credit_service)]
CreationSessionServiceDep = Annotated[
    CreationSessionService, Depends(get_creation_session_service)
]
EntitlementServiceDep = Annotated[EntitlementService, Depends(get_entitlement_service)]
GenerationServiceDep = Annotated[GenerationService, Depends(get_generation_service)]
AssetServiceDep = Annotated[AssetService, Depends(get_asset_service)]
BillingServiceDep = Annotated[BillingService, Depends(get_billing_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
ShowcaseServiceDep = Annotated[ShowcaseService, Depends(get_showcase_service)]
DevServiceDep = Annotated[DevService, Depends(get_dev_service)]


# --- auth ---


async def get_optional_user_id(
    request: Request,
    settings: SettingsDep,
    auth: AuthServiceDep,
    x_dev_user_id: Annotated[str | None, Header(alias="X-Dev-User-Id")] = None,
) -> str | None:
    """
    Resolve current user from session cookie, or X-Dev-User-Id in development.
    """
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    user = await auth.resolve_session_token(raw)
    if user is not None:
        return user.id

    if settings.allow_dev_auth and settings.is_development and x_dev_user_id:
        return x_dev_user_id
    return None


async def require_user_id(
    user_id: Annotated[str | None, Depends(get_optional_user_id)],
) -> str:
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_REQUIRED", "message": "Login required"},
        )
    return user_id


OptionalUserIdDep = Annotated[str | None, Depends(get_optional_user_id)]
UserIdDep = Annotated[str, Depends(require_user_id)]
