"""Pollo AI video generation client (text-to-video / image-to-video)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.models.enums import PolloTaskStatus

logger = logging.getLogger(__name__)

# Provider-facing input URL TTL (Pollo fetches after submit)
PROVIDER_IMAGE_URL_EXPIRES = 6 * 3600


class PolloClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base = (settings.pollo_base_url or "https://pollo.ai/api/platform").rstrip("/")
        self._key = settings.pollo_api_key
        self._webhook_secret = settings.pollo_webhook_secret

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self._key,
        }

    @property
    def configured(self) -> bool:
        return bool(self._key)

    def build_text_input(
        self,
        *,
        prompt: str,
        aspect_ratio: str,
        length: int,
        resolution: str,
        generate_audio: bool = False,
        seed: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "prompt": prompt,
            "aspectRatio": aspect_ratio,
            "length": length,
            "resolution": resolution,
            "generateAudio": generate_audio,
        }
        if seed is not None:
            body["seed"] = seed
        return body

    def build_image_input(
        self,
        *,
        image_url: str,
        prompt: str | None,
        length: int,
        resolution: str,
        generate_audio: bool = False,
        seed: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "image": image_url,
            "length": length,
            "resolution": resolution,
            "generateAudio": generate_audio,
        }
        if prompt:
            body["prompt"] = prompt
        if seed is not None:
            body["seed"] = seed
        return body

    async def submit(
        self,
        *,
        model_ref: str,
        input_payload: dict[str, Any],
        webhook_url: str | None = None,
    ) -> dict[str, Any]:
        """
        POST /generation/pollo/{model_ref}
        Returns { taskId, status }.
        """
        if not self._key:
            logger.warning("POLLO_API_KEY empty; returning stub task")
            return {
                "taskId": f"stub-pollo-{model_ref[-6:]}",
                "status": PolloTaskStatus.SUCCEED.value,
                "generations": [
                    {
                        "id": "stub-gen",
                        "status": PolloTaskStatus.SUCCEED.value,
                        "failMsg": None,
                        "url": "https://example.com/stub-video.mp4",
                        "mediaType": "video",
                    }
                ],
                "_stub": True,
            }

        path = f"/generation/pollo/{model_ref}"
        body: dict[str, Any] = {"input": input_payload}
        if webhook_url:
            body["webhookUrl"] = webhook_url

        url = f"{self._base}{path}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=self._headers(), json=body)
            if resp.status_code >= 400:
                logger.error(
                    "Pollo submit failed status=%s body=%s",
                    resp.status_code,
                    resp.text[:500],
                )
            resp.raise_for_status()
            return self._unwrap(resp.json())

    async def query(self, task_id: str) -> dict[str, Any]:
        """GET /generation/{taskId}/status"""
        if not self._key or task_id.startswith("stub-"):
            return {
                "taskId": task_id,
                "credit": 0,
                "generations": [
                    {
                        "id": "stub-gen",
                        "status": PolloTaskStatus.SUCCEED.value,
                        "failMsg": None,
                        "url": "https://example.com/stub-video.mp4",
                        "mediaType": "video",
                    }
                ],
                "_stub": True,
            }

        url = f"{self._base}/generation/{task_id}/status"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers=self._headers())
            if resp.status_code >= 400:
                logger.error(
                    "Pollo query failed status=%s body=%s",
                    resp.status_code,
                    resp.text[:500],
                )
            resp.raise_for_status()
            return self._unwrap(resp.json())

    @staticmethod
    def _unwrap(payload: dict[str, Any]) -> dict[str, Any]:
        """
        Pollo may return either OpenAPI flat shape or a platform envelope:

          { "code": "SUCCESS", "message": "success", "data": { "taskId": "...", ... } }
        """
        if not isinstance(payload, dict):
            return payload
        data = payload.get("data")
        if isinstance(data, dict) and (
            "taskId" in data or "generations" in data or "status" in data
        ):
            # preserve envelope meta for debugging without shadowing task fields
            merged = dict(data)
            if "code" in payload:
                merged["_envelope_code"] = payload.get("code")
            if "message" in payload:
                merged["_envelope_message"] = payload.get("message")
            return merged
        return payload

    def verify_webhook_signature(
        self,
        *,
        webhook_id: str,
        webhook_timestamp: str,
        body: bytes | str,
        signature: str,
    ) -> bool:
        """
        HMAC-SHA256 over `{id}.{timestamp}.{body}` with base64-decoded secret.
        Header X-Webhook-Signature is base64.
        """
        secret = self._webhook_secret
        if not secret:
            logger.warning("POLLO_WEBHOOK_SECRET empty; rejecting signed webhook verify")
            return False
        raw_body = body if isinstance(body, str) else body.decode("utf-8")
        signed_content = f"{webhook_id}.{webhook_timestamp}.{raw_body}"
        try:
            secret_bytes = base64.b64decode(secret)
        except Exception:
            # allow plain secret for local dev
            secret_bytes = secret.encode("utf-8")
        computed = base64.b64encode(
            hmac.new(secret_bytes, signed_content.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")
        # Header may contain one or multiple signatures
        candidates = [s.strip() for s in signature.split(",") if s.strip()]
        return any(hmac.compare_digest(computed, c) for c in candidates)

    @staticmethod
    def extract_video_url(payload: dict[str, Any]) -> str | None:
        generations = payload.get("generations") or []
        for gen in generations:
            if not isinstance(gen, dict):
                continue
            if gen.get("status") == PolloTaskStatus.SUCCEED.value and gen.get("url"):
                return str(gen["url"])
        # first url fallback
        for gen in generations:
            if isinstance(gen, dict) and gen.get("url"):
                return str(gen["url"])
        return None

    @staticmethod
    def aggregate_status(payload: dict[str, Any]) -> str:
        """Best-effort overall status from status response."""
        generations = payload.get("generations") or []
        if not generations:
            return str(payload.get("status") or PolloTaskStatus.PROCESSING.value)
        statuses = [
            str(g.get("status") or "")
            for g in generations
            if isinstance(g, dict)
        ]
        if any(s == PolloTaskStatus.FAILED.value for s in statuses):
            return PolloTaskStatus.FAILED.value
        if statuses and all(s == PolloTaskStatus.SUCCEED.value for s in statuses):
            return PolloTaskStatus.SUCCEED.value
        if any(s == PolloTaskStatus.PROCESSING.value for s in statuses):
            return PolloTaskStatus.PROCESSING.value
        if any(s == PolloTaskStatus.WAITING.value for s in statuses):
            return PolloTaskStatus.WAITING.value
        return statuses[0] if statuses else PolloTaskStatus.PROCESSING.value
