from typing import Literal

from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded"] = Field(description="Overall API health")
    database: Literal["up", "down"]
    service: str = "renderpop-server"
