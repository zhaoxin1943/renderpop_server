"""Asset upload API shapes (I2V input images)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import AssetStatus, AssetType


class CreateUploadIntentBody(BaseModel):
    purpose: str = Field(
        default="video_input",
        description="video_input | ...",
    )
    filename: str = Field(description="Original filename, used for extension")
    content_type: str = Field(description="image/jpeg | image/png | image/webp")
    byte_size: int | None = Field(default=None, ge=1, le=20_000_000)


class UploadIntentResponse(BaseModel):
    asset_id: str
    upload_url: str
    storage_key: str
    headers: dict[str, str]
    expires_in: int
    asset_type: AssetType
    status: AssetStatus


class CompleteUploadBody(BaseModel):
    pass


class AssetResponse(BaseModel):
    asset_id: str
    asset_type: AssetType
    status: AssetStatus
    mime_type: str | None = None
    byte_size: int | None = None
