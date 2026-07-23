from sqlmodel import Field

from app.models.base import TimestampedModel


class CreationSession(TimestampedModel, table=True):
    """A durable thread that groups one owner's generation tasks."""

    __tablename__ = "creation_sessions"

    user_id: str | None = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        max_length=36,
        nullable=True,
    )
    visitor_id: str | None = Field(
        default=None,
        foreign_key="anonymous_visitors.id",
        index=True,
        max_length=36,
        nullable=True,
    )
