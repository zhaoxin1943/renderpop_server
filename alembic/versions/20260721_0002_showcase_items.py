"""showcase_items for homepage waterfall

Revision ID: 20260721_0002
Revises: 20260721_0001
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0002"
down_revision: str | None = "20260721_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "showcase_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(length=1024), nullable=False),
        sa.Column(
            "aspect_ratio",
            sa.String(length=16),
            server_default="9:16",
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
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
    op.create_index("ix_showcase_items_sort_order", "showcase_items", ["sort_order"])
    op.create_index("ix_showcase_items_is_active", "showcase_items", ["is_active"])
    op.create_index("ix_showcase_items_deleted_at", "showcase_items", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_showcase_items_deleted_at", table_name="showcase_items")
    op.drop_index("ix_showcase_items_is_active", table_name="showcase_items")
    op.drop_index("ix_showcase_items_sort_order", table_name="showcase_items")
    op.drop_table("showcase_items")
