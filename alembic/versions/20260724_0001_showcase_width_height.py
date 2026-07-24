"""add width and height to showcase_items

Revision ID: 20260724_0001
Revises: 20260723_0002
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0001"
down_revision: str | None = "20260723_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "showcase_items",
        sa.Column("width", sa.Integer(), nullable=True),
    )
    op.add_column(
        "showcase_items",
        sa.Column("height", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("showcase_items", "height")
    op.drop_column("showcase_items", "width")
