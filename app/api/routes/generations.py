from fastapi import APIRouter, BackgroundTasks, Header, Query, Response, status

from app.core.deps import GenerationServiceDep, OptionalUserIdDep, SettingsDep
from app.core.errors import AppError
from app.models.enums import TaskType
from app.schemas.generation import (
    CreateGenerationBody,
    GenerationOptionsResponse,
    GenerationQuoteBody,
    GenerationQuoteResponse,
    GenerationTaskResponse,
)
from app.workers.tasks import run_generation_job

router = APIRouter(prefix="/v1/generations", tags=["generations"])


@router.get("/options", response_model=GenerationOptionsResponse)
async def list_generation_options(
    service: GenerationServiceDep,
    job_type: TaskType | None = Query(
        default=None,
        description="Optional filter, e.g. PRO_IMAGE_TO_IMAGE",
    ),
) -> GenerationOptionsResponse:
    """Frontend catalogs: supported aspect_ratios / resolutions per job_type."""
    return await service.list_job_options(job_type=job_type)


@router.post("/quote", response_model=GenerationQuoteResponse)
async def quote_generation(
    body: GenerationQuoteBody,
    service: GenerationServiceDep,
    user_id: OptionalUserIdDep,
) -> GenerationQuoteResponse:
    return await service.quote(
        user_id=user_id,
        task_type=body.job_type,
        length=body.length,
        resolution=body.resolution,
        generate_audio=body.generate_audio,
    )


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
        raise AppError(
            "VALIDATION_ERROR",
            "Idempotency-Key or client_request_id required",
            422,
        )

    try:
        task = await service.create_task(
            user_id=user_id,
            visitor_id=x_visitor_id,
            task_type=body.job_type,
            prompt=body.prompt,
            aspect_ratio=body.aspect_ratio,
            idempotency_key=key,
            length=body.length,
            resolution=body.resolution,
            generate_audio=body.generate_audio,
            input_asset_id=body.input_asset_id,
            template_id=body.template_id,
            reference_video_asset_id=body.reference_video_asset_id,
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
    return await service.to_public(task)


async def _run_inline(task_id: str) -> None:
    """Dev fallback without Dramatiq worker process."""
    from app.core.config import get_settings
    from app.core.db import get_session_factory
    from app.service.composition import build_generation_service

    factory = get_session_factory()
    async with factory() as session:
        try:
            gen = build_generation_service(session, get_settings())
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
    return await service.to_public(task)


@router.post("/{job_id}/poll", response_model=GenerationTaskResponse)
async def poll_generation(
    job_id: str,
    service: GenerationServiceDep,
    user_id: OptionalUserIdDep,
) -> GenerationTaskResponse:
    """Manual poll of provider (also used by worker)."""
    await service.get_task(job_id, user_id=user_id)
    task = await service.poll_provider(job_id)
    return await service.to_public(task)
