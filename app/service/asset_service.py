"""User asset upload intents (private S3) for IMAGE_VIDEO / I2I / Dance inputs."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import PurePosixPath

from app.core.errors import AuthRequired, NotFound, ValidationFailed
from app.models.asset import Asset
from app.models.base import new_id
from app.models.enums import AssetStatus, AssetType
from app.providers.s3 import PRESIGNED_PUT_EXPIRES, S3Storage
from app.schemas.asset import AssetResponse, UploadIntentResponse
from app.repo.base import BaseRepo

logger = logging.getLogger(__name__)

_ALLOWED_IMAGE_TYPES = frozenset(
    {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
    }
)
_ALLOWED_VIDEO_TYPES = frozenset(
    {
        "video/mp4",
        "video/webm",
        "video/quicktime",
    }
)

# Image inputs (I2V / I2I / Dance photo): 20 MB
_MAX_IMAGE_BYTES = 20_000_000
# Dance reference video upload: 100 MB
_MAX_VIDEO_BYTES = 100_000_000

_IMAGE_PURPOSES = frozenset({"video_input", "input_image", "dance_photo"})
_VIDEO_PURPOSES = frozenset({"dance_reference_video", "input_video"})


class AssetService:
    def __init__(self, session_repo: BaseRepo, s3: S3Storage) -> None:
        self._session = session_repo.session
        self._s3 = s3

    async def create_upload_intent(
        self,
        *,
        user_id: str | None,
        filename: str,
        content_type: str,
        byte_size: int | None = None,
        purpose: str = "video_input",
    ) -> UploadIntentResponse:
        if not user_id:
            raise AuthRequired("Login required to upload")
        content_type = (content_type or "").split(";")[0].strip().lower()
        if content_type == "image/jpg":
            content_type = "image/jpeg"

        purpose = (purpose or "video_input").strip()
        if purpose in _IMAGE_PURPOSES:
            if content_type not in _ALLOWED_IMAGE_TYPES:
                raise ValidationFailed(
                    f"content_type must be one of {sorted(_ALLOWED_IMAGE_TYPES)}"
                )
            if byte_size is not None and byte_size > _MAX_IMAGE_BYTES:
                raise ValidationFailed(
                    f"image must be at most {_MAX_IMAGE_BYTES} bytes"
                )
            asset_type = AssetType.INPUT_IMAGE
            max_bytes = _MAX_IMAGE_BYTES
        elif purpose in _VIDEO_PURPOSES:
            if content_type not in _ALLOWED_VIDEO_TYPES:
                raise ValidationFailed(
                    f"content_type must be one of {sorted(_ALLOWED_VIDEO_TYPES)}"
                )
            if byte_size is not None and byte_size > _MAX_VIDEO_BYTES:
                raise ValidationFailed(
                    f"video must be at most {_MAX_VIDEO_BYTES} bytes"
                )
            asset_type = AssetType.INPUT_VIDEO
            max_bytes = _MAX_VIDEO_BYTES
        else:
            raise ValidationFailed(
                "unsupported purpose; use video_input | input_image | dance_photo "
                "| dance_reference_video | input_video"
            )

        if not self._s3.configured:
            logger.warning("S3 not configured; creating stub upload intent")

        ext = _ext_from_filename(filename, content_type)
        asset_id = new_id()
        storage_key = self._s3.build_input_key(
            asset_id=asset_id,
            user_id=user_id,
            ext=ext,
        )
        asset = Asset(
            id=asset_id,
            owner_user_id=user_id,
            asset_type=asset_type,
            storage_key=storage_key,
            mime_type=content_type,
            byte_size=byte_size,
            status=AssetStatus.UPLOADING,
        )
        self._session.add(asset)
        await self._session.flush()

        if self._s3.configured:
            upload_url = await self._s3.presign_put(
                storage_key, content_type=content_type
            )
        else:
            upload_url = f"https://example.com/stub-upload/{storage_key}"

        return UploadIntentResponse(
            asset_id=asset_id,
            upload_url=upload_url,
            storage_key=storage_key,
            headers={"Content-Type": content_type},
            expires_in=PRESIGNED_PUT_EXPIRES,
            asset_type=asset_type,
            status=AssetStatus.UPLOADING,
            max_byte_size=max_bytes,
        )

    async def complete_upload(
        self, *, asset_id: str, user_id: str | None
    ) -> AssetResponse:
        if not user_id:
            raise AuthRequired()
        asset = await self._session.get(Asset, asset_id)
        if asset is None or asset.owner_user_id != user_id:
            raise NotFound("Asset not found")
        if asset.status == AssetStatus.READY:
            return self._to_public(asset)
        if asset.status not in (AssetStatus.UPLOADING, AssetStatus.PENDING_TRANSFER):
            raise ValidationFailed(f"cannot complete asset in status {asset.status}")

        # MVP: trust client completed PUT (no HEAD check yet)
        asset.status = AssetStatus.READY
        await self._session.flush()
        return self._to_public(asset)

    def _to_public(self, asset: Asset) -> AssetResponse:
        return AssetResponse(
            asset_id=asset.id,
            asset_type=asset.asset_type,
            status=asset.status,
            mime_type=asset.mime_type,
            byte_size=asset.byte_size,
        )


def _ext_from_filename(filename: str, content_type: str) -> str:
    suffix = PurePosixPath(filename or "").suffix.lstrip(".").lower()
    if suffix in ("jpg", "jpeg", "png", "webp", "mp4", "webm", "mov"):
        if suffix == "jpeg":
            return "jpg"
        if suffix == "mov":
            return "mp4"
        return suffix
    guessed = mimetypes.guess_extension(content_type) or ".bin"
    return guessed.lstrip(".")[:16] or "bin"
