"""
Seed default generation models (Pollo video + RunningHub image / I2I / Dance).

  conda activate renderpop
  python -m scripts.seed_generation_models
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.commerce import (
    DANCE_ASPECT_RATIOS,
    DANCE_DEFAULT_ASPECT_RATIO,
    DANCE_PRICING_VERSION,
    DEFAULT_ASPECT_RATIO,
    FAST_ASPECT_RATIOS,
    FAST_I2I_ASPECT_RATIOS,
    FAST_I2I_DEFAULT_ASPECT_RATIO,
    IMAGE_FAST_I2I_PRICING_VERSION,
    IMAGE_FAST_PRICING_VERSION,
    IMAGE_PRO_I2I_PRICING_VERSION,
    IMAGE_PRO_PRICING_VERSION,
    PRO_I2I_ASPECT_RATIOS,
    PRO_I2I_DEFAULT_ASPECT_RATIO,
    PRO_I2I_DEFAULT_RESOLUTION,
    PRO_I2I_RESOLUTIONS,
    PRO_IMAGE_CREDITS,
    RH_DANCE_APP_ID,
    RH_DANCE_MODEL_CODE,
    RH_FAST_APP_ID,
    RH_FAST_I2I_APP_ID,
    RH_FAST_I2I_MODEL_CODE,
    RH_FAST_IMAGE_MODEL_CODE,
    RH_PRO_APP_ID,
    RH_PRO_I2I_APP_ID,
    RH_PRO_I2I_MODEL_CODE,
    RH_PRO_IMAGE_MODEL_CODE,
    VIDEO_DEFAULT_ASPECT_RATIO,
    VIDEO_DEFAULT_LENGTH,
    VIDEO_DEFAULT_RESOLUTION,
    VIDEO_MODEL_CODE,
    VIDEO_PRICING_VERSION,
    VIDEO_PROVIDER_MODEL_REF,
    VIDEO_SUPPORTED_ASPECT_RATIOS,
    VIDEO_SUPPORTED_LENGTHS,
    VIDEO_SUPPORTED_RESOLUTIONS,
    default_dance_pricing_config,
    default_rh_fixed_pricing_config,
    default_rh_quota_pricing_config,
    default_video_pricing_config,
)
from app.core.db import dispose_engine, get_session_factory
from app.models.base import new_id
from app.models.enums import (
    GenerationModelStatus,
    GenerationProvider,
    ModelModality,
    PricingType,
    TaskType,
)
from app.models.generation_model import GenerationModel


async def _upsert(session: AsyncSession, *, code: str, payload: dict[str, Any]) -> None:
    stmt = select(GenerationModel).where(GenerationModel.code == code)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row:
        for k, v in payload.items():
            setattr(row, k, v)
        print(f"updated {code}")
    else:
        session.add(GenerationModel(id=new_id(), code=code, **payload))
        print(f"created {code}")


async def upsert_pollo_video(session: AsyncSession) -> None:
    await _upsert(
        session,
        code=VIDEO_MODEL_CODE,
        payload=dict(
            name="Pollo 2.0 Video",
            display_name="AI Video",
            modality=ModelModality.VIDEO,
            task_types=[TaskType.TEXT_VIDEO.value, TaskType.IMAGE_VIDEO.value],
            provider=GenerationProvider.POLLO,
            provider_model_ref=VIDEO_PROVIDER_MODEL_REF,
            status=GenerationModelStatus.ACTIVE,
            is_default=True,
            sort_order=10,
            supported_lengths=list(VIDEO_SUPPORTED_LENGTHS),
            supported_resolutions=list(VIDEO_SUPPORTED_RESOLUTIONS),
            supported_aspect_ratios=list(VIDEO_SUPPORTED_ASPECT_RATIOS),
            supports_audio=True,
            supports_image_input=True,
            supports_text_input=True,
            default_length=VIDEO_DEFAULT_LENGTH,
            default_resolution=VIDEO_DEFAULT_RESOLUTION,
            default_aspect_ratio=VIDEO_DEFAULT_ASPECT_RATIO,
            default_generate_audio=False,
            pricing_type=PricingType.FORMULA,
            pricing_config=default_video_pricing_config(),
            pricing_version=VIDEO_PRICING_VERSION,
            estimated_wait_seconds=90,
            config_version="1",
        ),
    )


async def upsert_rh_models(session: AsyncSession) -> None:
    await _upsert(
        session,
        code=RH_FAST_IMAGE_MODEL_CODE,
        payload=dict(
            name="RunningHub Fast Text-to-Image",
            display_name="Fast Image",
            modality=ModelModality.IMAGE,
            task_types=[TaskType.FAST_IMAGE.value],
            provider=GenerationProvider.RUNNINGHUB,
            provider_model_ref=RH_FAST_APP_ID,
            status=GenerationModelStatus.ACTIVE,
            is_default=True,
            sort_order=20,
            supported_lengths=None,
            supported_resolutions=None,
            supported_aspect_ratios=list(FAST_ASPECT_RATIOS),
            supports_audio=False,
            supports_image_input=False,
            supports_text_input=True,
            default_length=None,
            default_resolution=None,
            default_aspect_ratio=DEFAULT_ASPECT_RATIO,
            default_generate_audio=False,
            pricing_type=PricingType.FIXED,
            pricing_config=default_rh_quota_pricing_config(
                requires_login=False,
                pricing_version=IMAGE_FAST_PRICING_VERSION,
            ),
            pricing_version=IMAGE_FAST_PRICING_VERSION,
            estimated_wait_seconds=30,
            config_version="1",
        ),
    )
    await _upsert(
        session,
        code=RH_PRO_IMAGE_MODEL_CODE,
        payload=dict(
            name="RunningHub Pro Text-to-Image",
            display_name="Pro Image",
            modality=ModelModality.IMAGE,
            task_types=[TaskType.PRO_IMAGE.value],
            provider=GenerationProvider.RUNNINGHUB,
            provider_model_ref=RH_PRO_APP_ID,
            status=GenerationModelStatus.ACTIVE,
            is_default=True,
            sort_order=21,
            supported_lengths=None,
            supported_resolutions=None,
            supported_aspect_ratios=list(FAST_ASPECT_RATIOS),
            supports_audio=False,
            supports_image_input=False,
            supports_text_input=True,
            default_length=None,
            default_resolution=None,
            default_aspect_ratio=DEFAULT_ASPECT_RATIO,
            default_generate_audio=False,
            pricing_type=PricingType.FIXED,
            pricing_config=default_rh_fixed_pricing_config(
                credits=PRO_IMAGE_CREDITS,
                requires_login=True,
                pricing_version=IMAGE_PRO_PRICING_VERSION,
            ),
            pricing_version=IMAGE_PRO_PRICING_VERSION,
            estimated_wait_seconds=45,
            config_version="1",
        ),
    )
    await _upsert(
        session,
        code=RH_FAST_I2I_MODEL_CODE,
        payload=dict(
            name="RunningHub Free Image-to-Image",
            display_name="Fast Image-to-Image",
            modality=ModelModality.IMAGE,
            task_types=[TaskType.FAST_IMAGE_TO_IMAGE.value],
            provider=GenerationProvider.RUNNINGHUB,
            provider_model_ref=RH_FAST_I2I_APP_ID,
            status=GenerationModelStatus.ACTIVE,
            is_default=True,
            sort_order=22,
            supported_lengths=None,
            supported_resolutions=None,
            supported_aspect_ratios=list(FAST_I2I_ASPECT_RATIOS),
            supports_audio=False,
            supports_image_input=True,
            supports_text_input=True,
            default_length=None,
            default_resolution=None,
            default_aspect_ratio=FAST_I2I_DEFAULT_ASPECT_RATIO,
            default_generate_audio=False,
            pricing_type=PricingType.FIXED,
            pricing_config=default_rh_quota_pricing_config(
                requires_login=True,
                pricing_version=IMAGE_FAST_I2I_PRICING_VERSION,
            ),
            pricing_version=IMAGE_FAST_I2I_PRICING_VERSION,
            estimated_wait_seconds=40,
            config_version="1",
        ),
    )
    await _upsert(
        session,
        code=RH_PRO_I2I_MODEL_CODE,
        payload=dict(
            name="RunningHub Pro Image-to-Image",
            display_name="Pro Image-to-Image",
            modality=ModelModality.IMAGE,
            task_types=[TaskType.PRO_IMAGE_TO_IMAGE.value],
            provider=GenerationProvider.RUNNINGHUB,
            provider_model_ref=RH_PRO_I2I_APP_ID,
            status=GenerationModelStatus.ACTIVE,
            is_default=True,
            sort_order=23,
            supported_lengths=None,
            supported_resolutions=list(PRO_I2I_RESOLUTIONS),
            supported_aspect_ratios=list(PRO_I2I_ASPECT_RATIOS),
            supports_audio=False,
            supports_image_input=True,
            supports_text_input=True,
            default_length=None,
            default_resolution=PRO_I2I_DEFAULT_RESOLUTION,
            default_aspect_ratio=PRO_I2I_DEFAULT_ASPECT_RATIO,
            default_generate_audio=False,
            pricing_type=PricingType.FIXED,
            pricing_config=default_rh_fixed_pricing_config(
                credits=PRO_IMAGE_CREDITS,
                requires_login=True,
                pricing_version=IMAGE_PRO_I2I_PRICING_VERSION,
            ),
            pricing_version=IMAGE_PRO_I2I_PRICING_VERSION,
            estimated_wait_seconds=50,
            config_version="1",
        ),
    )
    await _upsert(
        session,
        code=RH_DANCE_MODEL_CODE,
        payload=dict(
            name="RunningHub Dance Video",
            display_name="AI Dance",
            modality=ModelModality.VIDEO,
            task_types=[TaskType.DANCE_VIDEO.value],
            provider=GenerationProvider.RUNNINGHUB,
            provider_model_ref=RH_DANCE_APP_ID,
            status=GenerationModelStatus.ACTIVE,
            is_default=True,
            sort_order=30,
            supported_lengths=None,
            supported_resolutions=None,
            supported_aspect_ratios=list(DANCE_ASPECT_RATIOS),
            supports_audio=False,
            supports_image_input=True,
            supports_text_input=False,
            default_length=None,
            default_resolution=None,
            default_aspect_ratio=DANCE_DEFAULT_ASPECT_RATIO,
            default_generate_audio=False,
            pricing_type=PricingType.FIXED,
            pricing_config=default_dance_pricing_config(),
            pricing_version=DANCE_PRICING_VERSION,
            estimated_wait_seconds=300,
            config_version="1",
        ),
    )


async def main() -> None:
    factory = get_session_factory()
    async with factory() as session:
        await upsert_pollo_video(session)
        await upsert_rh_models(session)
        await session.commit()
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
