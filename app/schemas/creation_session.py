from datetime import datetime

from pydantic import BaseModel

from app.schemas.generation import GenerationTaskResponse


class CreationSessionResponse(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    tasks: list[GenerationTaskResponse] = []


class LatestCreationSessionResponse(BaseModel):
    session: CreationSessionResponse | None = None
