"""Unit tests for Generation Task Dispatcher, Priorities, Queue Timeout, and RH 5 Concurrency Limit."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import GenerationProvider, PlanCode, TaskStatus, TaskType
from app.models.generation_task import GenerationTask
from app.schemas.generation import GenerationTaskResponse
from app.service.generation_service import _PLAN_PRIORITIES, GenerationService


def test_plan_priority_values() -> None:
    assert _PLAN_PRIORITIES[PlanCode.PRO] == 3000
    assert _PLAN_PRIORITIES[PlanCode.CREATOR] == 2000
    assert _PLAN_PRIORITIES[PlanCode.FREE] == 1000
    assert _PLAN_PRIORITIES[PlanCode.VISITOR] == 500


def test_generation_task_priority_default() -> None:
    task = GenerationTask(
        id="task-1",
        task_type=TaskType.FAST_IMAGE,
        prompt="test prompt",
        aspect_ratio="1:1",
        idempotency_key="idemp-1",
    )
    assert task.priority == 1000
    assert task.status == TaskStatus.CREATED


def test_generation_task_response_queue_position_field() -> None:
    resp = GenerationTaskResponse(
        job_id="job-123",
        task_type=TaskType.PRO_IMAGE,
        status=TaskStatus.QUEUED,
        prompt="a test prompt",
        aspect_ratio="16:9",
        queue_position=3,
    )
    assert resp.queue_position == 3
    assert resp.status == TaskStatus.QUEUED


@pytest.mark.asyncio
async def test_dispatch_pending_jobs_rh_limit_and_timeout() -> None:
    repo = AsyncMock()
    credits = AsyncMock()
    entitlements = AsyncMock()
    settings = MagicMock()

    now = datetime.now(UTC)

    # 1. Mock expired task (queued > 20 mins ago)
    expired_task = GenerationTask(
        id="task-expired",
        task_type=TaskType.PRO_IMAGE,
        status=TaskStatus.QUEUED,
        prompt="old task",
        aspect_ratio="1:1",
        idempotency_key="idemp-exp",
        credits_reserved=12,
        credit_reservation_id="res-1",
        provider=GenerationProvider.RUNNINGHUB,
        created_at=now - timedelta(minutes=25),
    )
    repo.fetch_expired_queued_tasks.return_value = [expired_task]

    # 2. Currently 3 running tasks on RunningHub -> Available slots = 5 - 3 = 2
    repo.count_active_by_provider.return_value = 3

    # Queued RH tasks ready to dispatch
    rh_task1 = GenerationTask(
        id="task-rh-1",
        task_type=TaskType.PRO_IMAGE,
        status=TaskStatus.QUEUED,
        prompt="p1",
        aspect_ratio="1:1",
        idempotency_key="key-rh-1",
        priority=3000,
        provider=GenerationProvider.RUNNINGHUB,
    )
    rh_task2 = GenerationTask(
        id="task-rh-2",
        task_type=TaskType.PRO_IMAGE,
        status=TaskStatus.QUEUED,
        prompt="p2",
        aspect_ratio="1:1",
        idempotency_key="key-rh-2",
        priority=2000,
        provider=GenerationProvider.RUNNINGHUB,
    )
    repo.fetch_next_queued_tasks.return_value = [rh_task1, rh_task2]

    # Pollo queued tasks
    pollo_task = GenerationTask(
        id="task-pollo-1",
        task_type=TaskType.TEXT_VIDEO,
        status=TaskStatus.QUEUED,
        prompt="v1",
        aspect_ratio="16:9",
        idempotency_key="key-pollo-1",
        priority=1000,
        provider=GenerationProvider.POLLO,
    )
    repo.fetch_all_queued_tasks_by_provider.return_value = [pollo_task]

    service = GenerationService(
        generation_repo=repo,
        credit_service=credits,
        entitlement_service=entitlements,
        settings=settings,
        rh=MagicMock(),
        pollo=MagicMock(),
        s3=MagicMock(),
    )

    dispatched = await service.dispatch_pending_jobs()

    # Expired task should be updated and credits released
    assert expired_task.status == TaskStatus.EXPIRED
    assert expired_task.failure_code == "QUEUE_TIMEOUT"
    credits.release_reservation.assert_called_once_with(task_id="task-expired")

    # Limit check: fetch_next_queued_tasks should be called with limit=2 (5 - 3 active)
    repo.fetch_next_queued_tasks.assert_called_once_with(GenerationProvider.RUNNINGHUB, limit=2)

    # Dispatched tasks should be transitioned to SUBMITTING
    assert rh_task1.status == TaskStatus.SUBMITTING
    assert rh_task2.status == TaskStatus.SUBMITTING
    assert pollo_task.status == TaskStatus.SUBMITTING
    assert set(dispatched) == {"task-rh-1", "task-rh-2", "task-pollo-1"}
