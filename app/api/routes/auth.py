from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.core.deps import SettingsDep
from app.schemas.me import MeResponse

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.get("/me", response_model=MeResponse)
async def me() -> MeResponse:
    """Placeholder until Google OAuth + session store land."""
    return MeResponse(authenticated=False, user=None)


@router.get("/google/start")
async def google_start(
    settings: SettingsDep,
    return_to: str = Query(default="/"),
) -> RedirectResponse:
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    # Full OAuth state + callback exchange ships with session implementation.
    raise HTTPException(
        status_code=501,
        detail="Google OAuth start is scaffolded; wire state store next",
    )
