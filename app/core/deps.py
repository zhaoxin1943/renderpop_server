"""
FastAPI dependency injection wiring.

Layer rule:
  api  -> depends on service (and optionally session for rare cases)
  service -> depends on repo(s) + shared session
  repo -> depends on shared AsyncSession only

One request => one MySQL AsyncSession (from get_db_session).
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_db_session
from app.repo.health_repo import HealthRepo
from app.service.health_service import HealthService

# --- primitives ---

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_session(session: SessionDep) -> AsyncGenerator[AsyncSession, None]:
    """Alias so callers can Depend(get_session) if preferred."""
    yield session


# --- repos (bind to request session) ---


def get_health_repo(session: SessionDep) -> HealthRepo:
    return HealthRepo(session)


HealthRepoDep = Annotated[HealthRepo, Depends(get_health_repo)]


# --- services ---


def get_health_service(repo: HealthRepoDep) -> HealthService:
    return HealthService(repo)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
