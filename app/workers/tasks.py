"""
Dramatiq actors.

Import this module from the worker CLI so actors are registered:
  dramatiq app.workers.tasks

Actors are async; they open their own short-lived AsyncSession
(worker has no HTTP request scope).
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
    """Smoke actor: verify Redis queue + async MySQL from worker process."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(text("SELECT 1"))
        ok = result.scalar_one() == 1
        await session.commit()
    logger.info("ping_worker database=%s", "up" if ok else "down")
    return {"database": "up" if ok else "down"}


@dramatiq.actor(queue_name="generation", max_retries=2, time_limit=1_800_000)
async def run_generation_job(job_id: str) -> None:
    """
    Placeholder for image/video/dance generation.

    Future: load job from MySQL, call provider, transfer to S3, ledger compensate.
    time_limit is 30 minutes (ms) to cover ~20min video jobs.
    """
    logger.info("run_generation_job received job_id=%s (not implemented)", job_id)
