"""S3 private media storage: upload from provider URLs + presigned download."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import mimetypes
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import boto3
import httpx
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings
from app.models.enums import TransferStatus

logger = logging.getLogger(__name__)

# How long generated result URLs are valid for the client.
PRESIGNED_GET_EXPIRES = 3600


@dataclass(frozen=True)
class TransferResult:
    status: TransferStatus
    storage_key: str | None = None
    mime_type: str | None = None
    byte_size: int | None = None
    checksum_sha256: str | None = None
    source_url: str | None = None
    error: str | None = None


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._bucket = settings.s3_bucket_name
        self._prefix = (settings.s3_asset_prefix or "media").strip().strip("/")
        self._region = settings.aws_region
        self._client: BaseClient | None = None

    @property
    def configured(self) -> bool:
        return bool(
            self._bucket
            and self._settings.aws_access_key_id
            and self._settings.aws_secret_access_key
        )

    def _get_client(self) -> BaseClient:
        if self._client is None:
            kwargs: dict[str, Any] = {"region_name": self._region}
            if self._settings.aws_access_key_id and self._settings.aws_secret_access_key:
                kwargs["aws_access_key_id"] = self._settings.aws_access_key_id
                kwargs["aws_secret_access_key"] = self._settings.aws_secret_access_key
            self._client = boto3.client("s3", **kwargs)
        return self._client

    def build_output_key(
        self,
        *,
        task_id: str,
        user_id: str | None,
        visitor_id: str | None = None,
        ext: str = "png",
    ) -> str:
        owner = user_id or visitor_id or "anon"
        safe_ext = (ext or "bin").lstrip(".").lower()[:16] or "bin"
        return f"{self._prefix}/outputs/{owner}/{task_id}/{uuid4().hex}.{safe_ext}"

    async def transfer_from_url(
        self,
        *,
        source_url: str,
        task_id: str,
        user_id: str | None,
        visitor_id: str | None = None,
    ) -> TransferResult:
        """Download a temporary provider URL and put the object in private S3."""
        if not source_url:
            return TransferResult(status=TransferStatus.FAILED, error="empty source_url")
        if not self.configured:
            logger.warning("S3 not configured; skipping transfer task=%s", task_id)
            return TransferResult(
                status=TransferStatus.SKIPPED,
                source_url=source_url,
                error="S3 credentials or bucket not configured",
            )

        try:
            body, content_type = await self._download(source_url)
        except Exception as exc:
            logger.exception("download failed task=%s url=%s", task_id, source_url[:120])
            return TransferResult(
                status=TransferStatus.FAILED,
                source_url=source_url,
                error=f"download failed: {exc}",
            )

        ext = _guess_ext(content_type, source_url)
        key = self.build_output_key(
            task_id=task_id,
            user_id=user_id,
            visitor_id=visitor_id,
            ext=ext,
        )
        checksum = hashlib.sha256(body).hexdigest()
        mime = content_type or mimetypes.types_map.get(f".{ext}", "application/octet-stream")

        try:
            await asyncio.to_thread(
                self._put_object,
                key=key,
                body=body,
                content_type=mime,
            )
        except (BotoCoreError, ClientError, OSError) as exc:
            logger.exception("S3 put failed task=%s key=%s", task_id, key)
            return TransferResult(
                status=TransferStatus.FAILED,
                source_url=source_url,
                error=f"s3 put failed: {exc}",
            )

        return TransferResult(
            status=TransferStatus.SUCCEEDED,
            storage_key=key,
            mime_type=mime,
            byte_size=len(body),
            checksum_sha256=checksum,
            source_url=source_url,
        )

    async def _download(self, url: str) -> tuple[bytes, str | None]:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type")
            if content_type:
                content_type = content_type.split(";")[0].strip()
            return resp.content, content_type

    def _put_object(self, *, key: str, body: bytes, content_type: str) -> None:
        self._get_client().put_object(
            Bucket=self._bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            # Private by default; bucket policy should block public ACL.
            ServerSideEncryption="AES256",
        )

    async def presign_get(
        self,
        storage_key: str,
        *,
        expires_in: int = PRESIGNED_GET_EXPIRES,
    ) -> str:
        if not self.configured:
            raise RuntimeError("S3 not configured")
        return await asyncio.to_thread(
            self._presign_get_sync,
            storage_key,
            expires_in,
        )

    def _presign_get_sync(self, storage_key: str, expires_in: int) -> str:
        return self._get_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": storage_key},
            ExpiresIn=expires_in,
        )


def _guess_ext(content_type: str | None, url: str) -> str:
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if ext:
            return ext.lstrip(".")
        mapping = {
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/gif": "gif",
            "video/mp4": "mp4",
        }
        if content_type in mapping:
            return mapping[content_type]
    path = urlparse(url).path
    if "." in path.rsplit("/", 1)[-1]:
        return path.rsplit(".", 1)[-1][:16]
    return "png"


@lru_cache
def get_s3_storage() -> S3Storage:
    from app.core.config import get_settings

    return S3Storage(get_settings())
