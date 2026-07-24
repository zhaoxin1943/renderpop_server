from fastapi import APIRouter, Header, status

from app.core.deps import CreationSessionServiceDep, GenerationServiceDep, OptionalUserIdDep
from app.models.creation_session import CreationSession
from app.schemas.creation_session import (
    CreationSessionListResponse,
    CreationSessionResponse,
    LatestCreationSessionResponse,
)

router = APIRouter(prefix="/v1/creation-sessions", tags=["creation-sessions"])


async def _to_public(
    creation_session: CreationSession,
    *,
    sessions: CreationSessionServiceDep,
    generations: GenerationServiceDep,
) -> CreationSessionResponse:
    tasks = await sessions.list_tasks(creation_session.id)
    return CreationSessionResponse(
        id=creation_session.id,
        created_at=creation_session.created_at,
        updated_at=creation_session.updated_at,
        tasks=[await generations.to_public(task) for task in tasks],
    )


@router.post("", response_model=CreationSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_creation_session(
    sessions: CreationSessionServiceDep,
    user_id: OptionalUserIdDep,
    x_visitor_id: str | None = Header(default=None, alias="X-Visitor-Id"),
) -> CreationSessionResponse:
    creation_session = await sessions.create(user_id=user_id, visitor_id=x_visitor_id)
    return CreationSessionResponse(
        id=creation_session.id,
        created_at=creation_session.created_at,
        updated_at=creation_session.updated_at,
    )


@router.get("/latest", response_model=LatestCreationSessionResponse)
async def get_latest_creation_session(
    sessions: CreationSessionServiceDep,
    generations: GenerationServiceDep,
    user_id: OptionalUserIdDep,
    x_visitor_id: str | None = Header(default=None, alias="X-Visitor-Id"),
) -> LatestCreationSessionResponse:
    creation_session = await sessions.get_latest(user_id=user_id, visitor_id=x_visitor_id)
    if creation_session is None:
        return LatestCreationSessionResponse()
    return LatestCreationSessionResponse(
        session=await _to_public(
            creation_session,
            sessions=sessions,
            generations=generations,
        )
    )


@router.get("", response_model=CreationSessionListResponse)
async def list_creation_sessions(
    sessions: CreationSessionServiceDep,
    generations: GenerationServiceDep,
    user_id: OptionalUserIdDep,
    x_visitor_id: str | None = Header(default=None, alias="X-Visitor-Id"),
) -> CreationSessionListResponse:
    owned_sessions = await sessions.list_owned(user_id=user_id, visitor_id=x_visitor_id)
    return CreationSessionListResponse(
        sessions=[
            await _to_public(session, sessions=sessions, generations=generations)
            for session in owned_sessions
        ]
    )


@router.get("/{session_id}", response_model=CreationSessionResponse)
async def get_creation_session(
    session_id: str,
    sessions: CreationSessionServiceDep,
    generations: GenerationServiceDep,
    user_id: OptionalUserIdDep,
    x_visitor_id: str | None = Header(default=None, alias="X-Visitor-Id"),
) -> CreationSessionResponse:
    creation_session = await sessions.get_owned(
        session_id,
        user_id=user_id,
        visitor_id=x_visitor_id,
    )
    public_session = await _to_public(
        creation_session,
        sessions=sessions,
        generations=generations,
    )
    if not public_session.tasks:
        from app.core.errors import NotFound
        raise NotFound("Creation session not found")
    return public_session
