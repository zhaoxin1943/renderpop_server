from fastapi import APIRouter, Request

from app.core.deps import GenerationServiceDep
from app.schemas.generation import RunningHubWebhookResponse

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
