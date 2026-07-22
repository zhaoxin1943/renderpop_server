from urllib.parse import parse_qs, urlparse

import pytest

from app.core.config import Settings
from app.core.errors import AuthRequired, ValidationFailed
from app.service.auth_service import AuthService


class UnusedUserRepo:
    """The tested helpers do not need persistence."""


def make_service() -> AuthService:
    settings = Settings(
        session_secret="a-long-enough-test-session-secret",
        google_client_id="test-client-id",
        google_client_secret="test-client-secret",
        google_redirect_uri="http://localhost:3000/api/v1/auth/google/callback",
    )
    return AuthService(UnusedUserRepo(), settings)  # type: ignore[arg-type]


def test_google_authorize_url_round_trips_safe_return_path() -> None:
    service = make_service()

    url = service.build_google_authorize_url(return_to="/account?tab=credits")
    query = parse_qs(urlparse(url).query)

    assert query["client_id"] == ["test-client-id"]
    assert query["redirect_uri"] == [
        "http://localhost:3000/api/v1/auth/google/callback"
    ]
    assert service.parse_oauth_state(query["state"][0]) == "/account?tab=credits"


@pytest.mark.parametrize("return_to", ["https://bad.example", "//bad.example", "\\\\bad"])
def test_google_authorize_url_rejects_external_return_path(return_to: str) -> None:
    service = make_service()

    url = service.build_google_authorize_url(return_to=return_to)
    state = parse_qs(urlparse(url).query)["state"][0]

    assert service.parse_oauth_state(state) == "/"


def test_google_authorize_url_requires_complete_google_config() -> None:
    settings = Settings(
        session_secret="a-long-enough-test-session-secret",
        google_client_id="test-client-id",
        google_client_secret="",
    )
    service = AuthService(UnusedUserRepo(), settings)  # type: ignore[arg-type]

    with pytest.raises(AuthRequired):
        service.parse_oauth_state("invalid")
    with pytest.raises(ValidationFailed, match="Google OAuth is not configured"):
        service.build_google_authorize_url(return_to="/")
