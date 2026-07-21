from fastapi import APIRouter

from app.core.deps import HealthServiceDep
from app.schemas.common import LiveStatus
from app.schemas.health import HealthStatus

router = APIRouter()


@router.get("/health", response_model=HealthStatus)
async def health(service: HealthServiceDep) -> HealthStatus:
    """Liveness + MySQL ping via service → repo (async, shared session)."""
    return await service.check()


@router.get("/health/live", response_model=LiveStatus)
async def live() -> LiveStatus:
    """Process liveness without DB (for k8s/docker)."""
    return LiveStatus(status="alive")
