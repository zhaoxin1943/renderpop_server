"""
Seed default generation models (AI Video / Pollo).

  conda activate renderpop
  python -m scripts.seed_generation_models
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.commerce import (
    VIDEO_DEFAULT_ASPECT_RATIO,
    VIDEO_DEFAULT_LENGTH,
    VIDEO_DEFAULT_RESOLUTION,
    VIDEO_MODEL_CODE,
    VIDEO_PRICING_VERSION,
    VIDEO_PROVIDER_MODEL_REF,
    VIDEO_SUPPORTED_ASPECT_RATIOS,
    VIDEO_SUPPORTED_LENGTHS,
    VIDEO_SUPPORTED_RESOLUTIONS,
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


async def upsert_pollo_video(session: AsyncSession) -> None:
    stmt = select(GenerationModel).where(GenerationModel.code == VIDEO_MODEL_CODE)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    payload = dict(
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
    )
    if row:
        for k, v in payload.items():
            setattr(row, k, v)
        print(f"updated {VIDEO_MODEL_CODE}")
    else:
        session.add(GenerationModel(id=new_id(), code=VIDEO_MODEL_CODE, **payload))
        print(f"created {VIDEO_MODEL_CODE}")


async def main() -> None:
    factory = get_session_factory()
    async with factory() as session:
        await upsert_pollo_video(session)
        await session.commit()
    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
