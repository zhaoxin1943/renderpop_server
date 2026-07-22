"""User asset upload intents (private S3) for IMAGE_VIDEO inputs."""

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
        if content_type not in _ALLOWED_IMAGE_TYPES:
            raise ValidationFailed(
                f"content_type must be one of {sorted(_ALLOWED_IMAGE_TYPES)}"
            )
        if purpose not in ("video_input", "input_image"):
            raise ValidationFailed("unsupported purpose")

        if not self._s3.configured:
            # Dev stub path: still create asset row with a fake key so flow can be tested
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
            asset_type=AssetType.INPUT_IMAGE,
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
            asset_type=AssetType.INPUT_IMAGE,
            status=AssetStatus.UPLOADING,
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
    if suffix in ("jpg", "jpeg", "png", "webp"):
        return "jpg" if suffix == "jpeg" else suffix
    guessed = mimetypes.guess_extension(content_type) or ".jpg"
    return guessed.lstrip(".")[:16] or "jpg"
