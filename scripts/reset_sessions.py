"""
Clear session-related tables (creation_sessions, sessions, anonymous_visitors)
and nullify or clear associated creation_session_id references in generation_tasks for dev testing.

Usage:
  conda activate renderpop
  python -m scripts.reset_sessions
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
        
        # Clear creation sessions
        res_cs = await session.execute(text("DELETE FROM creation_sessions;"))
        
        # Clear auth sessions
        res_s = await session.execute(text("DELETE FROM sessions;"))
        
        # Clear anonymous visitors
        res_v = await session.execute(text("DELETE FROM anonymous_visitors;"))
        
        # Detach creation_session_id references from generation_tasks if any exist
        await session.execute(text("UPDATE generation_tasks SET creation_session_id = NULL WHERE creation_session_id IS NOT NULL;"))
        
        await session.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        await session.commit()
        
        print("Successfully reset all session-related database tables:")
        print(f"  - Deleted {res_cs.rowcount} row(s) from 'creation_sessions'")
        print(f"  - Deleted {res_s.rowcount} row(s) from 'sessions'")
        print(f"  - Deleted {res_v.rowcount} row(s) from 'anonymous_visitors'")
        print("  - Cleared creation_session_id references in 'generation_tasks'")

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
