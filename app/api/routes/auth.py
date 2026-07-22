from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.core.deps import AuthServiceDep, OptionalUserIdDep, SettingsDep
from app.core.errors import AppError, AuthRequired
from app.schemas.auth import GoogleClientConfigResponse, GoogleCredentialBody
from app.schemas.me import MeResponse, UserSummary
from app.service.auth_service import SESSION_COOKIE_NAME

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.get("/me", response_model=MeResponse)
async def auth_me(
    user_id: OptionalUserIdDep,
    auth: AuthServiceDep,
) -> MeResponse:
    return await auth.get_me(user_id)


@router.get("/google/start")
async def google_start(
    auth: AuthServiceDep,
    settings: SettingsDep,
    return_to: str = Query("/", alias="return_to"),
) -> RedirectResponse:
    if not settings.google_client_id or not settings.google_client_secret:
        raise AppError("OAUTH_NOT_CONFIGURED", "Google OAuth is not configured", 503)
    url = auth.build_google_authorize_url(return_to=return_to)
    return RedirectResponse(url=url, status_code=302)


@router.get("/google/config", response_model=GoogleClientConfigResponse)
async def google_client_config(settings: SettingsDep) -> GoogleClientConfigResponse:
    """Expose the OAuth client ID used by the browser-side GIS library."""
    if not settings.google_client_id:
        raise AppError("OAUTH_NOT_CONFIGURED", "Google OAuth is not configured", 503)
    return GoogleClientConfigResponse(client_id=settings.google_client_id)


@router.post("/google/credential", response_model=MeResponse)
async def google_credential_login(
    body: GoogleCredentialBody,
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    settings: SettingsDep,
    origin: str | None = Header(default=None),
    x_requested_with: str | None = Header(default=None),
) -> MeResponse:
    """Complete a Google Identity Services button or One Tap sign-in."""
    if origin != settings.web_origin or x_requested_with != "XMLHttpRequest":
        raise AppError("INVALID_OAUTH_ORIGIN", "Invalid Google sign-in request", 403)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    user, raw_token = await auth.complete_google_credential_login(
        credential=body.credential,
        ip=client_ip,
        user_agent=user_agent,
    )
    response.set_cookie(value=raw_token, **auth.session_cookie_kwargs())
    return MeResponse(
        authenticated=True,
        user=UserSummary(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
        ),
    )


@router.get("/google/callback")
async def google_callback(
    request: Request,
    auth: AuthServiceDep,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    if error:
        dest = auth.absolute_web_url(f"/sign-in?error={error}")
        return RedirectResponse(url=dest, status_code=302)
    if not code or not state:
        raise AuthRequired("Missing OAuth code or state")

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    try:
        _user, raw_token, return_to = await auth.complete_google_login(
            code=code,
            state=state,
            ip=client_ip,
            user_agent=user_agent,
        )
    except AppError:
        dest = auth.absolute_web_url("/sign-in?error=oauth_failed")
        return RedirectResponse(url=dest, status_code=302)

    # Relative path keeps the browser on the web origin (Next rewrite).
    if not return_to.startswith("/"):
        return_to = "/"
    redirect = RedirectResponse(url=return_to, status_code=302)
    cookie_kwargs = auth.session_cookie_kwargs()
    redirect.set_cookie(value=raw_token, **cookie_kwargs)
    return redirect


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    auth: AuthServiceDep,
    settings: SettingsDep,
) -> dict[str, bool]:
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    await auth.logout(raw)
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
    )
    return {"ok": True}
