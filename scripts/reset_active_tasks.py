"""
Clear all records in generation_tasks and generation_task_attempts tables for dev testing.

Usage:
  conda activate renderpop
  python -m scripts.reset_active_tasks
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running as module from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.db import dispose_engine, get_session_factory


async def main() -> None:
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        await session.execute(text("DELETE FROM generation_attempts;"))
        result = await session.execute(text("DELETE FROM generation_tasks;"))
        await session.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        await session.commit()
        print(f"Successfully cleared generation_tasks and generation_attempts tables (deleted {result.rowcount} tasks).")

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
