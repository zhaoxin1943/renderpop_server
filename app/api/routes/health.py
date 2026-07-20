from fastapi import APIRouter

from app.core.deps import HealthServiceDep
from app.schemas.health import HealthStatus

router = APIRouter()


@router.get("/health", response_model=HealthStatus)
async def health(service: HealthServiceDep) -> HealthStatus:
    """Liveness + MySQL ping via service → repo (async, shared session)."""
    return await service.check()


@router.get("/health/live")
async def live() -> dict[str, str]:
    """Process liveness without DB (for k8s/docker)."""
    return {"status": "alive"}
