"""create dance_templates table

Revision ID: 20260724_0002
Revises: 20260724_0001
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260724_0002"
down_revision: str | None = "20260724_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dance_templates",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column(
            "duration_seconds",
            sa.Integer(),
            server_default="10",
            nullable=False,
        ),
        sa.Column("video_url", sa.String(length=1024), nullable=False),
        sa.Column("poster_url", sa.String(length=1024), nullable=True),
        sa.Column(
            "aspect_ratio",
            sa.String(length=16),
            server_default="9:16",
            nullable=False,
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "is_trending",
            sa.Boolean(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.String(length=32),
            server_default="general",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dance_templates_sort_order", "dance_templates", ["sort_order"])
    op.create_index("ix_dance_templates_is_active", "dance_templates", ["is_active"])
    op.create_index("ix_dance_templates_is_trending", "dance_templates", ["is_trending"])
    op.create_index("ix_dance_templates_category", "dance_templates", ["category"])
    op.create_index("ix_dance_templates_deleted_at", "dance_templates", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_dance_templates_deleted_at", table_name="dance_templates")
    op.drop_index("ix_dance_templates_category", table_name="dance_templates")
    op.drop_index("ix_dance_templates_is_trending", table_name="dance_templates")
    op.drop_index("ix_dance_templates_is_active", table_name="dance_templates")
    op.drop_index("ix_dance_templates_sort_order", table_name="dance_templates")
    op.drop_table("dance_templates")
