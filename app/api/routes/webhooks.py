from typing import Any

from fastapi import APIRouter, Request

from app.core.deps import GenerationServiceDep

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/generation/runninghub")
async def runninghub_webhook(
    request: Request,
    service: GenerationServiceDep,
) -> dict[str, Any]:
    """RunningHub task completion callback (prefer over poll)."""
    payload = await request.json()
    task = await service.handle_provider_payload(payload)
    return {
        "ok": True,
        "job_id": task.id if task else None,
        "status": task.status if task else None,
    }
