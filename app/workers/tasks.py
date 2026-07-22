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


def _build_generation_service(session, settings):
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

    return GenerationService(
        GenerationRepo(session),
        CreditService(CreditRepo(session)),
        EntitlementService(
            SubscriptionRepo(session),
            UsageRepo(session),
            CreditService(CreditRepo(session)),
        ),
        settings,
        rh=RunningHubClient(settings),
        pollo=PolloClient(settings),
        s3=S3Storage(settings),
        model_repo=GenerationModelRepo(session),
    )


@dramatiq.actor(queue_name="generation", max_retries=2, time_limit=1_800_000)
async def run_generation_job(job_id: str) -> None:
    """Submit task to provider; poll until terminal if needed."""
    import asyncio

    from app.core.config import get_settings
    from app.models.enums import TaskStatus

    factory = get_session_factory()
    settings = get_settings()
    async with factory() as session:
        try:
            gen = _build_generation_service(session, settings)
            task = await gen.submit_to_provider(job_id)
            # Video jobs run longer than images — poll longer with larger interval
            if task.status == TaskStatus.PROCESSING and task.provider_task_id:
                is_video = gen.is_video_task(task)
                iterations = 60 if is_video else 30
                sleep_s = 5 if is_video else 2
                for _ in range(iterations):
                    await asyncio.sleep(sleep_s)
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

    factory = get_session_factory()
    settings = get_settings()
    async with factory() as session:
        try:
            gen = _build_generation_service(session, settings)
            task = await gen.poll_provider(job_id)
            await session.commit()
            logger.info("poll_generation_job job_id=%s status=%s", job_id, task.status)
        except Exception:
            await session.rollback()
            raise
