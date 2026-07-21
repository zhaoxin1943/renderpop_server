"""Google OAuth + server-side session cookies."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import Settings
from app.core.errors import AuthRequired, ValidationFailed
from app.models.base import new_id, utc_now
from app.models.identity import Identity
from app.models.session import Session
from app.models.user import User
from app.repo.user_repo import UserRepo

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "rp_session"
SESSION_TTL_DAYS = 30
OAUTH_STATE_MAX_AGE = 600  # seconds
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = "openid email profile"


class AuthService:
    def __init__(self, users: UserRepo, settings: Settings) -> None:
        self._users = users
        self._settings = settings

    def _state_serializer(self) -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(
            self._settings.session_secret,
            salt="renderpop-google-oauth",
        )

    def build_google_authorize_url(self, *, return_to: str) -> str:
        if not self._settings.google_client_id or not self._settings.google_client_secret:
            raise ValidationFailed("Google OAuth is not configured", code="OAUTH_NOT_CONFIGURED")
        safe_return = _safe_return_to(return_to)
        state = self._state_serializer().dumps(
            {"return_to": safe_return, "n": secrets.token_hex(8)}
        )
        params = {
            "client_id": self._settings.google_client_id,
            "redirect_uri": self._settings.google_redirect_uri,
            "response_type": "code",
            "scope": GOOGLE_SCOPES,
            "access_type": "online",
            "include_granted_scopes": "true",
            "prompt": "select_account",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def parse_oauth_state(self, state: str) -> str:
        try:
            data = self._state_serializer().loads(state, max_age=OAUTH_STATE_MAX_AGE)
        except SignatureExpired as exc:
            raise AuthRequired("OAuth state expired") from exc
        except BadSignature as exc:
            raise AuthRequired("Invalid OAuth state") from exc
        if not isinstance(data, dict):
            raise AuthRequired("Invalid OAuth state")
        return _safe_return_to(str(data.get("return_to") or "/"))

    async def complete_google_login(
        self,
        *,
        code: str,
        state: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        """
        Exchange code, upsert user/identity, create session.

        Returns (user, raw_session_token, return_to).
        """
        return_to = self.parse_oauth_state(state)
        profile = await self._exchange_google_code(code)
        user = await self._upsert_google_user(profile)
        raw_token = await self.create_session(
            user_id=user.id,
            ip=ip,
            user_agent=user_agent,
        )
        return user, raw_token, return_to

    async def _exchange_google_code(self, code: str) -> dict[str, Any]:
        if not self._settings.google_client_id or not self._settings.google_client_secret:
            raise ValidationFailed("Google OAuth is not configured", code="OAUTH_NOT_CONFIGURED")

        async with httpx.AsyncClient(timeout=30.0) as client:
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self._settings.google_client_id,
                    "client_secret": self._settings.google_client_secret,
                    "redirect_uri": self._settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            if token_resp.status_code >= 400:
                logger.warning(
                    "Google token exchange failed status=%s body=%s",
                    token_resp.status_code,
                    token_resp.text[:300],
                )
                raise AuthRequired("Google token exchange failed")
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise AuthRequired("Google token missing access_token")

            info_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if info_resp.status_code >= 400:
                logger.warning("Google userinfo failed status=%s", info_resp.status_code)
                raise AuthRequired("Failed to load Google profile")
            profile = info_resp.json()

        if not profile.get("sub"):
            raise AuthRequired("Google profile missing subject")
        if not profile.get("email"):
            raise AuthRequired("Google account email is required")
        if profile.get("email_verified") is False:
            raise AuthRequired("Google email is not verified")
        return profile

    async def _upsert_google_user(self, profile: dict[str, Any]) -> User:
        subject = str(profile["sub"])
        email = str(profile["email"]).strip().lower()
        display_name = profile.get("name") or profile.get("given_name")
        avatar_url = profile.get("picture")

        identity = await self._users.get_identity("google", subject)
        if identity:
            user = await self._users.get_by_id(identity.user_id)
            if user is None or user.deleted_at is not None or not user.is_active:
                raise AuthRequired("Account is not available")
            # Refresh profile fields lightly
            if display_name and user.display_name != display_name:
                user.display_name = str(display_name)[:255]
            if avatar_url and user.avatar_url != avatar_url:
                user.avatar_url = str(avatar_url)[:1024]
            if identity.email != email:
                identity.email = email
            await self._users.session.flush()
            return user

        # Link by email if user already exists (e.g. created via dev endpoint)
        user = await self._users.get_by_email(email)
        if user is None:
            user = User(
                id=new_id(),
                email=email,
                display_name=str(display_name)[:255] if display_name else None,
                avatar_url=str(avatar_url)[:1024] if avatar_url else None,
                status="ACTIVE",
                risk_level="LOW",
                is_active=True,
            )
            await self._users.create(user)
        else:
            if display_name and not user.display_name:
                user.display_name = str(display_name)[:255]
            if avatar_url and not user.avatar_url:
                user.avatar_url = str(avatar_url)[:1024]

        await self._users.create_identity(
            Identity(
                id=new_id(),
                user_id=user.id,
                provider="google",
                provider_subject=subject,
                email=email,
            )
        )
        return user

    async def create_session(
        self,
        *,
        user_id: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> str:
        raw = secrets.token_urlsafe(32)
        session = Session(
            id=new_id(),
            user_id=user_id,
            token_hash=_hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(days=SESSION_TTL_DAYS),
            ip=ip[:64] if ip else None,
            user_agent=user_agent[:2000] if user_agent else None,
        )
        await self._users.create_session(session)
        return raw

    async def resolve_session_token(self, raw_token: str | None) -> User | None:
        if not raw_token:
            return None
        row = await self._users.get_session_by_token_hash(_hash_token(raw_token))
        if row is None:
            return None
        now = utc_now()
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        if row.revoked_at is not None or exp <= now:
            return None
        user = await self._users.get_by_id(row.user_id)
        if user is None or user.deleted_at is not None or not user.is_active:
            return None
        if user.status != "ACTIVE":
            return None
        return user

    async def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        row = await self._users.get_session_by_token_hash(_hash_token(raw_token))
        if row and row.revoked_at is None:
            row.revoked_at = utc_now()
            await self._users.session.flush()

    def session_cookie_kwargs(self) -> dict[str, Any]:
        secure = self._settings.is_production
        return {
            "key": SESSION_COOKIE_NAME,
            "httponly": True,
            "secure": secure,
            "samesite": "lax",
            "path": "/",
            "max_age": SESSION_TTL_DAYS * 24 * 3600,
        }

    def absolute_web_url(self, path: str) -> str:
        base = self._settings.web_origin.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        return f"{base}{path}"


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _safe_return_to(value: str) -> str:
    """Only allow same-site relative paths (open-redirect safe)."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/"
    if "\\" in value or "://" in value:
        return "/"
    return value
