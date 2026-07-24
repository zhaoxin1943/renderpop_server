"""add priority column to generation_tasks table

Revision ID: 20260724_0003
Revises: 20260724_0002
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0003"
down_revision: str | None = "20260724_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_tasks",
        sa.Column(
            "priority",
            sa.Integer(),
            server_default="1000",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_generation_tasks_priority",
        "generation_tasks",
        ["priority"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_generation_tasks_priority", table_name="generation_tasks")
    op.drop_column("generation_tasks", "priority")
