from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.generation import GenerationTaskResponse


class CreationSessionResponse(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    tasks: list[GenerationTaskResponse] = Field(default_factory=list)


class LatestCreationSessionResponse(BaseModel):
    session: CreationSessionResponse | None = None


class CreationSessionListResponse(BaseModel):
    sessions: list[CreationSessionResponse] = Field(default_factory=list)
