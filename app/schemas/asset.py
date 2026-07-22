"""Asset upload API shapes (I2V / I2I / Dance inputs)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import AssetStatus, AssetType


class CreateUploadIntentBody(BaseModel):
    purpose: str = Field(
        default="video_input",
        description=(
            "video_input | input_image | dance_photo "
            "| dance_reference_video | input_video"
        ),
    )
    filename: str = Field(description="Original filename, used for extension")
    content_type: str = Field(
        description="image/jpeg|png|webp or video/mp4|webm|quicktime"
    )
    byte_size: int | None = Field(
        default=None,
        ge=1,
        le=100_000_000,
        description="Declared size; images max 20MB, videos max 100MB",
    )


class UploadIntentResponse(BaseModel):
    asset_id: str
    upload_url: str
    storage_key: str
    headers: dict[str, str]
    expires_in: int
    asset_type: AssetType
    status: AssetStatus
    max_byte_size: int | None = None


class CompleteUploadBody(BaseModel):
    pass


class AssetResponse(BaseModel):
    asset_id: str
    asset_type: AssetType
    status: AssetStatus
    mime_type: str | None = None
    byte_size: int | None = None
