from app.repo.health_repo import HealthRepo
from app.schemas.health import HealthStatus


class HealthService:
    def __init__(self, repo: HealthRepo) -> None:
        self._repo = repo

    async def check(self) -> HealthStatus:
        db_ok = await self._repo.ping_database()
        return HealthStatus(
            status="ok" if db_ok else "degraded",
            database="up" if db_ok else "down",
        )
