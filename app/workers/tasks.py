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
    from app.service.composition import build_generation_service

    return build_generation_service(session, settings)


@dramatiq.actor(queue_name="generation", max_retries=1)
async def dispatch_pending_jobs() -> None:
    """Trigger Dispatcher to check 20-min queue timeouts and fill free provider slots."""
    from app.core.config import get_settings

    factory = get_session_factory()
    settings = get_settings()
    async with factory() as session:
        try:
            gen = _build_generation_service(session, settings)
            dispatched = await gen.dispatch_pending_jobs()
            logger.info("dispatch_pending_jobs dispatched_count=%s", len(dispatched))
        except Exception:
            logger.exception("dispatch_pending_jobs failed")
            raise


@dramatiq.actor(queue_name="generation", max_retries=2, time_limit=1_800_000)
async def run_generation_job(job_id: str) -> None:
    """Submit task to provider; poll until terminal if needed."""
    import asyncio

    from app.core.config import get_settings
    from app.models.enums import TaskStatus

    factory = get_session_factory()
    settings = get_settings()
    try:
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
    finally:
        # Task finished or released slot -> dispatch next task in queue
        try:
            dispatch_pending_jobs.send()
        except Exception:
            logger.exception("Failed to trigger dispatch_pending_jobs after task execution")


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

