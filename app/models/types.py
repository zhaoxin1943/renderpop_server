"""Backward-compatible re-exports. Prefer ``app.models.base`` for new code."""

from app.models.base import (  # noqa: F401
    CreatedAtMixin,
    CreatedModel,
    IdMixin,
    SoftDeleteMixin,
    TimestampedModel,
    UpdatedAtMixin,
    new_id,
    utc_now,
)
