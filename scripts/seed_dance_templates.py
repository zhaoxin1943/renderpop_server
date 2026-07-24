"""Seed default dance templates into dance_templates table."""

import asyncio
import logging

from sqlalchemy import select

ASSET_ORIGIN = "https://s3.us-east-2.amazonaws.com/renderpop-assets/dance/templates"

INITIAL_TEMPLATES = [
    ("dance-01", "Blue Tempo", 13, 1, 10),
    ("dance-02", "Soft Bounce", 6, 2, 20),
    ("dance-03", "Midnight Step", 8, 3, 30),
    ("dance-04", "Pop Routine", 9, 4, 40),
    ("dance-05", "Ribbon Walk", 12, 5, 50),
    ("dance-06", "Balcony Beat", 10, 6, 60),
    ("dance-07", "After Dark", 8, 7, 70),
    ("dance-08", "Bodyline", 10, 8, 80),
    ("dance-09", "Side Step", 6, 9, 90),
]


async def seed() -> None:
    factory = get_session_factory()
    async with factory() as session:
        count_added = 0
        for item_id, title, duration, index, sort_order in INITIAL_TEMPLATES:
            stmt = select(DanceTemplate).where(DanceTemplate.id == item_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                template = DanceTemplate(
                    id=item_id,
                    title=title,
                    duration_seconds=duration,
                    video_url=f"{ASSET_ORIGIN}/{index}.mp4",
                    poster_url=f"{ASSET_ORIGIN}/{index}.png",
                    aspect_ratio="9:16",
                    sort_order=sort_order,
                    is_active=True,
                    is_trending=False,
                    category="general",
                )
                session.add(template)
                count_added += 1

        await session.commit()
        logger.info(f"Successfully seeded {count_added} dance templates.")


if __name__ == "__main__":
    asyncio.run(seed())
