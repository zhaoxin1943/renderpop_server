"""credits, membership, generation tasks, products env

Revision ID: 20260721_0001
Revises:
Create Date: 2026-07-21

Replaces prior face-swap-oriented draft schema. Safe on empty DB.
Creates all tables from SQLModel metadata (MVP bootstrap).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260721_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Import models so metadata is complete
    import app.models  # noqa: F401
    from sqlmodel import SQLModel

    bind = op.get_bind()
    SQLModel.metadata.create_all(bind=bind)


def downgrade() -> None:
    import app.models  # noqa: F401
    from sqlmodel import SQLModel

    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind=bind)
