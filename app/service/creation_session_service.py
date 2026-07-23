from app.core.errors import AuthRequired, NotFound
from app.models.anonymous_visitor import AnonymousVisitor
from app.models.base import utc_now
from app.models.creation_session import CreationSession
from app.models.generation_task import GenerationTask
from app.repo.creation_session_repo import CreationSessionRepo


class CreationSessionService:
    def __init__(self, repo: CreationSessionRepo) -> None:
        self._repo = repo

    async def _resolve_owner(
        self,
        *,
        user_id: str | None,
        visitor_id: str | None,
        create_visitor: bool,
    ) -> tuple[str | None, str | None]:
        if user_id:
            return user_id, None
        if not visitor_id:
            if create_visitor:
                raise AuthRequired("Visitor or user required")
            return None, None

        visitor = await self._repo.session.get(AnonymousVisitor, visitor_id)
        if visitor is None:
            if not create_visitor:
                return None, None
            visitor = AnonymousVisitor(id=visitor_id, last_seen_at=utc_now())
            self._repo.session.add(visitor)
            await self._repo.session.flush()
        else:
            visitor.last_seen_at = utc_now()
        return None, visitor.id

    async def create(
        self, *, user_id: str | None, visitor_id: str | None
    ) -> CreationSession:
        owner_user_id, owner_visitor_id = await self._resolve_owner(
            user_id=user_id,
            visitor_id=visitor_id,
            create_visitor=True,
        )
        return await self._repo.add(
            CreationSession(user_id=owner_user_id, visitor_id=owner_visitor_id)
        )

    async def get_latest(
        self, *, user_id: str | None, visitor_id: str | None
    ) -> CreationSession | None:
        owner_user_id, owner_visitor_id = await self._resolve_owner(
            user_id=user_id,
            visitor_id=visitor_id,
            create_visitor=False,
        )
        return await self._repo.get_latest(
            user_id=owner_user_id,
            visitor_id=owner_visitor_id,
        )

    async def get_owned(
        self,
        session_id: str,
        *,
        user_id: str | None,
        visitor_id: str | None,
    ) -> CreationSession:
        owner_user_id, owner_visitor_id = await self._resolve_owner(
            user_id=user_id,
            visitor_id=visitor_id,
            create_visitor=False,
        )
        creation_session = await self._repo.get_owned(
            session_id,
            user_id=owner_user_id,
            visitor_id=owner_visitor_id,
        )
        if creation_session is None:
            raise NotFound("Creation session not found")
        return creation_session

    async def list_tasks(self, session_id: str) -> list[GenerationTask]:
        return await self._repo.list_tasks(session_id)
