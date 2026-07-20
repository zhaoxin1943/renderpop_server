from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepo:
    """All repos receive the request-scoped AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
