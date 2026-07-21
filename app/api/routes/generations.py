from fastapi import APIRouter, BackgroundTasks, Header, Response, status

from app.core.deps import GenerationServiceDep, OptionalUserIdDep, SettingsDep
from app.core.errors import AppError
from app.schemas.generation import CreateGenerationBody, GenerationTaskResponse
from app.workers.tasks import run_generation_job

router = APIRouter(prefix="/v1/generations", tags=["generations"])


@router.post("", response_model=GenerationTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_generation(
    body: CreateGenerationBody,
    response: Response,
    service: GenerationServiceDep,
    user_id: OptionalUserIdDep,
    settings: SettingsDep,
    background: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_visitor_id: str | None = Header(default=None, alias="X-Visitor-Id"),
) -> GenerationTaskResponse:
    key = idempotency_key or body.client_request_id
    if not key:
        raise AppError("VALIDATION_ERROR", "Idempotency-Key or client_request_id required", 422)

    try:
        task = await service.create_task(
            user_id=user_id,
            visitor_id=x_visitor_id,
            task_type=body.job_type,
            prompt=body.prompt,
            aspect_ratio=body.aspect_ratio,
            idempotency_key=key,
        )
    except AppError:
        raise

    # Enqueue worker; fallback to background if broker unavailable
    try:
        run_generation_job.send(task.id)
    except Exception:
        if settings.is_development:
            background.add_task(_run_inline, task.id)
        else:
            raise

    response.status_code = status.HTTP_202_ACCEPTED
    return service.to_public(task)


async def _run_inline(task_id: str) -> None:
    """Dev fallback without Dramatiq worker process."""
    from app.core.config import get_settings
    from app.core.db import get_session_factory
    from app.providers.runninghub import RunningHubClient
    from app.repo.credit_repo import CreditRepo
    from app.repo.generation_repo import GenerationRepo
    from app.repo.subscription_repo import SubscriptionRepo
    from app.repo.usage_repo import UsageRepo
    from app.service.credit_service import CreditService
    from app.service.entitlement_service import EntitlementService
    from app.service.generation_service import GenerationService

    factory = get_session_factory()
    async with factory() as session:
        try:
            settings = get_settings()
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
            )
            await gen.submit_to_provider(task_id)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@router.get("/{job_id}", response_model=GenerationTaskResponse)
async def get_generation(
    job_id: str,
    service: GenerationServiceDep,
    user_id: OptionalUserIdDep,
) -> GenerationTaskResponse:
    task = await service.get_task(job_id, user_id=user_id)
    return service.to_public(task)


@router.post("/{job_id}/poll", response_model=GenerationTaskResponse)
async def poll_generation(
    job_id: str,
    service: GenerationServiceDep,
    user_id: OptionalUserIdDep,
) -> GenerationTaskResponse:
    """Manual poll of RunningHub (also used by worker)."""
    await service.get_task(job_id, user_id=user_id)
    task = await service.poll_provider(job_id)
    return service.to_public(task)
