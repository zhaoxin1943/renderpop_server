"""Public showcase (homepage waterfall) shapes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ShowcaseItemResponse(BaseModel):
    id: str
    title: str | None = None
    prompt: str
    image_url: str
    aspect_ratio: str = "9:16"
    width: int | None = None
    height: int | None = None


class ShowcaseListResponse(BaseModel):
    items: list[ShowcaseItemResponse] = Field(default_factory=list)
