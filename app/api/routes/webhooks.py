from fastapi import APIRouter, Request

from app.core.deps import GenerationServiceDep
from app.core.errors import AppError
from app.schemas.generation import PolloWebhookResponse, RunningHubWebhookResponse

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/generation/runninghub", response_model=RunningHubWebhookResponse)
async def runninghub_webhook(
    request: Request,
    service: GenerationServiceDep,
) -> RunningHubWebhookResponse:
    """RunningHub task completion callback (prefer over poll)."""
    payload = await request.json()
    task = await service.handle_provider_payload(payload)
    return RunningHubWebhookResponse(
        ok=True,
        job_id=task.id if task else None,
        status=task.status if task else None,
    )


@router.post("/generation/pollo", response_model=PolloWebhookResponse)
async def pollo_webhook(
    request: Request,
    service: GenerationServiceDep,
) -> PolloWebhookResponse:
    """
    Pollo task completion callback.

    Body is only {taskId, status}; on succeed we query status for video URL.
    """
    import json

    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise AppError("VALIDATION_ERROR", "invalid JSON body", 422) from exc

    try:
        task = await service.handle_pollo_webhook(
            payload=payload if isinstance(payload, dict) else {},
            webhook_id=request.headers.get("x-webhook-id"),
            webhook_timestamp=request.headers.get("x-webhook-timestamp"),
            signature=request.headers.get("x-webhook-signature"),
            raw_body=raw,
        )
    except AppError:
        raise

    return PolloWebhookResponse(
        ok=True,
        job_id=task.id if task else None,
        status=task.status if task else None,
    )
