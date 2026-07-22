"""Dance templates catalog (preset reference videos for DANCE_VIDEO)."""

from fastapi import APIRouter

from app.core.deps import GenerationServiceDep
from app.schemas.generation import DanceTemplatesResponse

router = APIRouter(prefix="/v1/dance", tags=["dance"])


@router.get("/templates", response_model=DanceTemplatesResponse)
async def list_dance_templates(
    service: GenerationServiceDep,
) -> DanceTemplatesResponse:
    """Active preset dance templates (node 275 video sources)."""
    return await service.list_dance_templates()
