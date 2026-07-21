"""RunningHub AI App client (Fast / Pro image)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.commerce import (
    FAST_ASPECT_SIZES,
    FAST_DEFAULT_SCALE_BY,
    PRO_DEFAULT_QUALITY,
    PRO_DEFAULT_RESOLUTION,
    RH_FAST_APP_ID,
    RH_PRO_APP_ID,
)
from app.core.config import Settings

logger = logging.getLogger(__name__)


class RunningHubClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base = settings.runninghub_base_url.rstrip("/")
        self._key = settings.runninghub_api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._key}",
        }

    @staticmethod
    def build_fast_node_list(*, prompt: str, aspect_ratio: str) -> list[dict[str, str]]:
        w, h = FAST_ASPECT_SIZES.get(aspect_ratio, FAST_ASPECT_SIZES["9:16"])
        return [
            {"nodeId": "76", "fieldName": "text", "fieldValue": prompt},
            {"nodeId": "27", "fieldName": "width", "fieldValue": str(w)},
            {"nodeId": "27", "fieldName": "height", "fieldValue": str(h)},
            {
                "nodeId": "68",
                "fieldName": "scale_by",
                "fieldValue": FAST_DEFAULT_SCALE_BY,
            },
        ]

    @staticmethod
    def build_pro_node_list( *, prompt: str, aspect_ratio: str) -> list[dict[str, str]]:
        return [
            {"nodeId": "3", "fieldName": "text", "fieldValue": prompt},
            {
                "nodeId": "1",
                "fieldName": "quality",
                "fieldValue": PRO_DEFAULT_QUALITY,
            },
            {
                "nodeId": "1",
                "fieldName": "resolution",
                "fieldValue": PRO_DEFAULT_RESOLUTION,
            },
            {
                "nodeId": "1",
                "fieldName": "aspectRatio",
                "fieldValue": aspect_ratio,
            },
        ]

    @staticmethod
    def input_params_for_fast(aspect_ratio: str) -> dict[str, Any]:
        w, h = FAST_ASPECT_SIZES.get(aspect_ratio, FAST_ASPECT_SIZES["9:16"])
        return {
            "width": w,
            "height": h,
            "scale_by": FAST_DEFAULT_SCALE_BY,
            "app_id": RH_FAST_APP_ID,
        }

    @staticmethod
    def input_params_for_pro(aspect_ratio: str) -> dict[str, Any]:
        return {
            "quality": PRO_DEFAULT_QUALITY,
            "resolution": PRO_DEFAULT_RESOLUTION,
            "aspect_ratio": aspect_ratio,
            "app_id": RH_PRO_APP_ID,
        }

    async def submit(
        self,
        *,
        app_id: str,
        node_info_list: list[dict[str, str]],
        webhook_url: str | None = None,
    ) -> dict[str, Any]:
        if not self._key:
            # Dev stub when key missing
            logger.warning("RUNNINGHUB_API_KEY empty; returning stub task")
            return {
                "taskId": f"stub-{app_id[-6:]}",
                "status": "SUCCESS",
                "results": [
                    {
                        "url": "https://example.com/stub.png",
                        "nodeId": "2",
                        "outputType": "png",
                        "text": None,
                    }
                ],
                "errorCode": "",
                "errorMessage": "",
                "_stub": True,
            }

        body: dict[str, Any] = {
            "nodeInfoList": node_info_list,
            "instanceType": "default",
            "usePersonalQueue": "false",
        }
        if webhook_url:
            body["webhookUrl"] = webhook_url

        url = f"{self._base}/openapi/v2/run/ai-app/{app_id}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=self._headers(), json=body)
            resp.raise_for_status()
            return resp.json()

    async def query(self, task_id: str) -> dict[str, Any]:
        if not self._key or task_id.startswith("stub-"):
            return {
                "taskId": task_id,
                "status": "SUCCESS",
                "results": [
                    {
                        "url": "https://example.com/stub.png",
                        "nodeId": "2",
                        "outputType": "png",
                        "text": None,
                    }
                ],
                "usage": {},
                "_stub": True,
            }

        url = f"{self._base}/openapi/v2/query"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                headers=self._headers(),
                json={"taskId": task_id},
            )
            resp.raise_for_status()
            return resp.json()



