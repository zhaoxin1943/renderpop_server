"""RunningHub AI App client (Fast / Pro image, I2I, Dance video)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.commerce import (
    DANCE_DEFAULT_ASPECT_RATIO,
    FAST_ASPECT_SIZES,
    FAST_DEFAULT_SCALE_BY,
    PRO_DEFAULT_QUALITY,
    PRO_DEFAULT_RESOLUTION,
    PRO_I2I_DEFAULT_RESOLUTION,
    RH_DANCE_APP_ID,
    RH_FAST_APP_ID,
    RH_FAST_I2I_APP_ID,
    RH_FAST_I2I_RATIO_SELECT,
    RH_PRO_APP_ID,
    RH_PRO_I2I_APP_ID,
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
    def build_pro_node_list(*, prompt: str, aspect_ratio: str) -> list[dict[str, str]]:
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
    def build_fast_i2i_node_list(
        *,
        prompt: str,
        image_url: str,
        aspect_ratio: str,
    ) -> list[dict[str, Any]]:
        """Free image-to-image: single required input (node 42).

        Optional image nodes 18 / 43 must still be present with fieldValue=null
        when unused (omitting them fails RH validation).
        """
        select = RH_FAST_I2I_RATIO_SELECT.get(
            aspect_ratio, RH_FAST_I2I_RATIO_SELECT["9:16"]
        )
        return [
            {
                "nodeId": "42",
                "fieldName": "image",
                "fieldValue": image_url,
            },
            {
                "nodeId": "18",
                "fieldName": "image",
                "fieldValue": None,
            },
            {
                "nodeId": "43",
                "fieldName": "image",
                "fieldValue": None,
            },
            {
                "nodeId": "41",
                "fieldName": "select",
                "fieldValue": select,
            },
            {
                "nodeId": "19",
                "fieldName": "prompt",
                "fieldValue": prompt,
            },
        ]

    @staticmethod
    def build_pro_i2i_node_list(
        *,
        prompt: str,
        image_url: str,
        aspect_ratio: str,
        resolution: str = PRO_I2I_DEFAULT_RESOLUTION,
    ) -> list[dict[str, Any]]:
        """Pro image-to-image: single required input (node 2).

        Optional image nodes 3 / 4 / 5 must still be present with fieldValue=null
        when unused (same pattern as free I2I nodes 18 / 43).
        """
        return [
            {
                "nodeId": "2",
                "fieldName": "image",
                "fieldValue": image_url,
            },
            {
                "nodeId": "3",
                "fieldName": "image",
                "fieldValue": None,
            },
            {
                "nodeId": "4",
                "fieldName": "image",
                "fieldValue": None,
            },
            {
                "nodeId": "5",
                "fieldName": "image",
                "fieldValue": None,
            },
            {
                "nodeId": "1",
                "fieldName": "resolution",
                "fieldValue": resolution,
            },
            {
                "nodeId": "1",
                "fieldName": "aspectRatio",
                "fieldValue": aspect_ratio,
            },
            {
                "nodeId": "1",
                "fieldName": "prompt",
                "fieldValue": prompt,
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

    @staticmethod
    def input_params_for_fast_i2i(*, aspect_ratio: str) -> dict[str, Any]:
        select = RH_FAST_I2I_RATIO_SELECT.get(
            aspect_ratio, RH_FAST_I2I_RATIO_SELECT["9:16"]
        )
        return {
            "app_id": RH_FAST_I2I_APP_ID,
            "aspect_ratio": aspect_ratio,
            "ratio_select": select,
            "has_input_image": True,
        }

    @staticmethod
    def input_params_for_pro_i2i(
        *,
        aspect_ratio: str,
        resolution: str = PRO_I2I_DEFAULT_RESOLUTION,
    ) -> dict[str, Any]:
        return {
            "app_id": RH_PRO_I2I_APP_ID,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "has_input_image": True,
        }

    @staticmethod
    def parse_aspect_ratio_parts(
        aspect_ratio: str,
    ) -> tuple[str, str]:
        """Split 'W:H' into (width, height) strings for RH nodes 451 / 450."""
        raw = (aspect_ratio or DANCE_DEFAULT_ASPECT_RATIO).strip()
        if ":" not in raw:
            raw = DANCE_DEFAULT_ASPECT_RATIO
        left, right = raw.split(":", 1)
        w, h = left.strip(), right.strip()
        if not w.isdigit() or not h.isdigit():
            w, h = DANCE_DEFAULT_ASPECT_RATIO.split(":")
        return w, h

    @staticmethod
    def build_dance_node_list(
        *,
        image_url: str,
        video_url: str,
        aspect_ratio: str = DANCE_DEFAULT_ASPECT_RATIO,
    ) -> list[dict[str, Any]]:
        """Photo-to-dance: node 299 photo, 275 reference video, 451/450 ratio.

        Ratio must match the reference video. All other nodes use docs/dance.md defaults.
        """
        ratio_w, ratio_h = RunningHubClient.parse_aspect_ratio_parts(aspect_ratio)
        return [
            {
                "nodeId": "535",
                "fieldName": "select",
                "fieldValue": "2",
                "description": "zip does not support cn sites",
            },
            {
                "nodeId": "293",
                "fieldName": "select",
                "fieldValue": "1",
                "description": "Posture calculation method",
            },
            {
                "nodeId": "497",
                "fieldName": "value",
                "fieldValue": "false",
                "description": "Pose 3, if neck length is on (default off)",
            },
            {
                "nodeId": "297",
                "fieldName": "value",
                "fieldValue": "1.0000000000000002",
                "description": "Posture Intensity",
            },
            {
                "nodeId": "370",
                "fieldName": "value",
                "fieldValue": "false",
                "description": "Camera movement switch (default is off)",
            },
            {
                "nodeId": "361",
                "fieldName": "value",
                "fieldValue": "1.0000000000000002",
                "description": "Camera movement intensity",
            },
            {
                "nodeId": "271",
                "fieldName": "value",
                "fieldValue": "false",
                "description": "Mask helmet mode",
            },
            {
                "nodeId": "265",
                "fieldName": "value",
                "fieldValue": "0.8000000000000002",
                "description": "Expression intensity",
            },
            {
                "nodeId": "266",
                "fieldName": "value",
                "fieldValue": "0.30000000000000004",
                "description": "Chest shaking amplitude",
            },
            {
                "nodeId": "499",
                "fieldName": "value",
                "fieldValue": "0",
                "description": "Skip how many frames ahead",
            },
            {
                "nodeId": "422",
                "fieldName": "value",
                "fieldValue": "840",
                "description": "Load frame limit",
            },
            {
                "nodeId": "264",
                "fieldName": "value",
                "fieldValue": "30",
                "description": "Frame rate",
            },
            {
                "nodeId": "470",
                "fieldName": "select",
                "fieldValue": "2",
                "description": "Resolution (recommended default)",
            },
            {
                "nodeId": "452",
                "fieldName": "value",
                "fieldValue": "true",
                "description": "Enable custom ratio",
            },
            {
                "nodeId": "451",
                "fieldName": "value",
                "fieldValue": ratio_w,
                "description": "Custom ratio width",
            },
            {
                "nodeId": "450",
                "fieldName": "value",
                "fieldValue": ratio_h,
                "description": "Custom ratio high",
            },
            {
                "nodeId": "275",
                "fieldName": "video",
                "fieldValue": video_url,
                "description": "Load reference video",
            },
            {
                "nodeId": "299",
                "fieldName": "image",
                "fieldValue": image_url,
                "description": "Load reference image",
            },
        ]

    @staticmethod
    def input_params_for_dance(
        *,
        aspect_ratio: str,
        template_id: str | None = None,
        reference_video_asset_id: str | None = None,
        template_video_url: str | None = None,
    ) -> dict[str, Any]:
        ratio_w, ratio_h = RunningHubClient.parse_aspect_ratio_parts(aspect_ratio)
        return {
            "app_id": RH_DANCE_APP_ID,
            "aspect_ratio": aspect_ratio,
            "ratio_width": ratio_w,
            "ratio_height": ratio_h,
            "template_id": template_id,
            "reference_video_asset_id": reference_video_asset_id,
            "template_video_url": template_video_url,
            "has_input_image": True,
            "has_reference_video": True,
        }

    @staticmethod
    def extract_video_url(payload: dict[str, Any]) -> str | None:
        """Pick mp4/webm from RH results (dance output)."""
        results = payload.get("results") or []
        if not isinstance(results, list):
            return None
        for item in results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "")
            out_type = str(item.get("outputType") or "").lower()
            if out_type in ("mp4", "webm") or url.lower().endswith((".mp4", ".webm")):
                return url or None
            if "/output/" in url and url:
                # fallback: first non-empty url if type missing
                pass
        for item in results:
            if isinstance(item, dict) and item.get("url"):
                url = str(item["url"])
                if any(ext in url.lower() for ext in (".mp4", ".webm", "video")):
                    return url
        return None

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
            "instanceType": "plus",
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



