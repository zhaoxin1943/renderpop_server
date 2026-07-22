"""
Out-of-request composition roots (workers, inline dev fallback).

Request path prefers FastAPI Depends in app.core.deps; this module shares the
same GenerationService graph when there is no request scope.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.providers.pollo import PolloClient
from app.providers.runninghub import RunningHubClient
from app.providers.s3 import S3Storage
from app.repo.credit_repo import CreditRepo
from app.repo.generation_model_repo import GenerationModelRepo
from app.repo.generation_repo import GenerationRepo
from app.repo.subscription_repo import SubscriptionRepo
from app.repo.usage_repo import UsageRepo
from app.service.credit_service import CreditService
from app.service.entitlement_service import EntitlementService
from app.service.generation_service import GenerationService


def build_generation_service(session: AsyncSession, settings: Settings) -> GenerationService:
    credits = CreditService(CreditRepo(session))
    return GenerationService(
        GenerationRepo(session),
        credits,
        EntitlementService(
            SubscriptionRepo(session),
            UsageRepo(session),
            credits,
        ),
        settings,
        rh=RunningHubClient(settings),
        pollo=PolloClient(settings),
        s3=S3Storage(settings),
        model_repo=GenerationModelRepo(session),
    )
