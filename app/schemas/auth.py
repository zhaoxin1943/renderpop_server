"""Request and public configuration shapes for authentication."""

from pydantic import BaseModel, Field


class GoogleClientConfigResponse(BaseModel):
    client_id: str


class GoogleCredentialBody(BaseModel):
    """A Google Identity Services ID token received in the browser."""

    credential: str = Field(min_length=20, max_length=20_000)
