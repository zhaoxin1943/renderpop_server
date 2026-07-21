"""
Dramatiq actors.

  dramatiq app.workers.tasks
"""

from __future__ import annotations

import logging

import dramatiq
from sqlalchemy import text

from app.core.db import get_session_factory
from app.workers.broker import ensure_broker

logger = logging.getLogger(__name__)

ensure_broker()


@dramatiq.actor(queue_name="default", max_retries=3)
async def ping_worker() -> dict[str, str]:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(text("SELECT 1"))
        ok = result.scalar_one() == 1
        await session.commit()
    logger.info("ping_worker database=%s", "up" if ok else "down")
    return {"database": "up" if ok else "down"}


@dramatiq.actor(queue_name="generation", max_retries=2, time_limit=1_800_000)
async def run_generation_job(job_id: str) -> None:
    """Submit task to RunningHub; poll until terminal if needed."""
    from app.core.config import get_settings
    from app.providers.runninghub import RunningHubClient
    from app.providers.s3 import S3Storage
    from app.repo.credit_repo import CreditRepo
    from app.repo.generation_repo import GenerationRepo
    from app.repo.subscription_repo import SubscriptionRepo
    from app.repo.usage_repo import UsageRepo
    from app.service.credit_service import CreditService
    from app.service.entitlement_service import EntitlementService
    from app.service.generation_service import GenerationService

    factory = get_session_factory()
    settings = get_settings()
    async with factory() as session:
        try:
            gen = GenerationService(
                GenerationRepo(session),
                CreditService(CreditRepo(session)),
                EntitlementService(
                    SubscriptionRepo(session),
                    UsageRepo(session),
                    CreditService(CreditRepo(session)),
                ),
                settings,
                rh=RunningHubClient(settings),
                s3=S3Storage(settings),
            )
            from app.models.enums import TaskStatus

            task = await gen.submit_to_provider(job_id)
            # Poll a few times if still processing
            if task.status == TaskStatus.PROCESSING and task.provider_task_id:
                import asyncio

                for _ in range(30):
                    await asyncio.sleep(2)
                    task = await gen.poll_provider(job_id)
                    if task.status in TaskStatus.terminal():
                        break
            await session.commit()
            logger.info("run_generation_job done job_id=%s status=%s", job_id, task.status)
        except Exception:
            await session.rollback()
            logger.exception("run_generation_job failed job_id=%s", job_id)
            raise


@dramatiq.actor(queue_name="generation", max_retries=1)
async def poll_generation_job(job_id: str) -> None:
    from app.core.config import get_settings
    from app.providers.runninghub import RunningHubClient
    from app.providers.s3 import S3Storage
    from app.repo.credit_repo import CreditRepo
    from app.repo.generation_repo import GenerationRepo
    from app.repo.subscription_repo import SubscriptionRepo
    from app.repo.usage_repo import UsageRepo
    from app.service.credit_service import CreditService
    from app.service.entitlement_service import EntitlementService
    from app.service.generation_service import GenerationService

    factory = get_session_factory()
    settings = get_settings()
    async with factory() as session:
        try:
            gen = GenerationService(
                GenerationRepo(session),
                CreditService(CreditRepo(session)),
                EntitlementService(
                    SubscriptionRepo(session),
                    UsageRepo(session),
                    CreditService(CreditRepo(session)),
                ),
                settings,
                rh=RunningHubClient(settings),
                s3=S3Storage(settings),
            )
            task = await gen.poll_provider(job_id)
            await session.commit()
            logger.info("poll_generation_job job_id=%s status=%s", job_id, task.status)
        except Exception:
            await session.rollback()
            raise
