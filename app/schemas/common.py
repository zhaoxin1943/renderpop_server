"""Shared API response / error shapes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Business and validation errors (HTTP 4xx/5xx)."""

    code: str = Field(description="Stable machine-readable error code")
    message: str = Field(description="Human-readable summary")
    details: Any | None = Field(default=None, description="Optional field-level or extra context")


class LiveStatus(BaseModel):
    status: str = "alive"
