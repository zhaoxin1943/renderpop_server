from typing import Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, Query, Response, status


from app.core.deps import (
    CreationSessionServiceDep,
    GenerationServiceDep,
    OptionalUserIdDep,
    SettingsDep,
    UserIdDep,
)
from app.core.errors import AppError
from app.models.enums import TaskType
from app.schemas.generation import (
    CreateGenerationBody,
    GeneratedAssetsResponse,
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


@router.get("/assets", response_model=GeneratedAssetsResponse)
async def list_generated_assets(
    service: GenerationServiceDep,
    user_id: UserIdDep,
    media_type: Literal["image", "video"] = Query(default="image"),
    limit: int = Query(default=60, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> GeneratedAssetsResponse:
    return await service.list_generated_assets(
        user_id=user_id,
        media_type=media_type,
        limit=limit,
        offset=offset,
    )


@router.delete("/assets/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_generated_asset(
    job_id: str,
    service: GenerationServiceDep,
    user_id: UserIdDep,
) -> None:
    await service.delete_generated_asset(user_id=user_id, job_id=job_id)


@router.get("/assets/{job_id}/download")
async def download_generated_asset(
    job_id: str,
    service: GenerationServiceDep,
    user_id: UserIdDep,
) -> Response:
    url = await service.get_generated_asset_download_url(user_id=user_id, job_id=job_id)
    async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
        res = await client.get(url)
        if res.status_code != 200:
            raise AppError("DOWNLOAD_FAILED", "Failed to download asset file", 500)

        content_type = res.headers.get("content-type", "application/octet-stream")
        ext = "mp4" if "video" in content_type else "png"
        filename = f"renderpop-{job_id[:8]}.{ext}"

        return Response(
            content=res.content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )



@router.post("", response_model=GenerationTaskResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_generation(
    body: CreateGenerationBody,
    response: Response,
    service: GenerationServiceDep,
    creation_sessions: CreationSessionServiceDep,
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
        if body.session_id:
            await creation_sessions.get_owned(
                body.session_id,
                user_id=user_id,
                visitor_id=x_visitor_id,
            )
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
            session_id=body.session_id,
        )
    except AppError:
        raise

    # Dispatch pending tasks (assigns slots and enqueues worker)
    try:
        await service.dispatch_pending_jobs()
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
