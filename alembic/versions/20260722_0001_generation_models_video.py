"""generation_models catalog + video fields on generation_tasks

Revision ID: 20260722_0001
Revises: 20260721_0003
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_0001"
down_revision: str | None = "20260721_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_models",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("modality", sa.String(length=32), nullable=False),
        sa.Column("task_types", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_model_ref", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="DRAFT", nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("supported_lengths", sa.JSON(), nullable=True),
        sa.Column("supported_resolutions", sa.JSON(), nullable=True),
        sa.Column("supported_aspect_ratios", sa.JSON(), nullable=True),
        sa.Column("supports_audio", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("supports_image_input", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("supports_text_input", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("default_length", sa.Integer(), nullable=True),
        sa.Column("default_resolution", sa.String(length=16), nullable=True),
        sa.Column("default_aspect_ratio", sa.String(length=16), nullable=True),
        sa.Column("default_generate_audio", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("pricing_type", sa.String(length=32), server_default="FORMULA", nullable=False),
        sa.Column("pricing_config", sa.JSON(), nullable=False),
        sa.Column("pricing_version", sa.String(length=32), server_default="1", nullable=False),
        sa.Column("estimated_wait_seconds", sa.Integer(), server_default="60", nullable=False),
        sa.Column("config_version", sa.String(length=32), server_default="1", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_generation_models_code"),
    )
    op.create_index("ix_generation_models_code", "generation_models", ["code"])
    op.create_index("ix_generation_models_modality", "generation_models", ["modality"])
    op.create_index("ix_generation_models_provider", "generation_models", ["provider"])
    op.create_index("ix_generation_models_status", "generation_models", ["status"])
    op.create_index("ix_generation_models_is_default", "generation_models", ["is_default"])
    op.create_index("ix_generation_models_deleted_at", "generation_models", ["deleted_at"])

    op.add_column(
        "generation_tasks",
        sa.Column("model_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "generation_tasks",
        sa.Column("model_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "generation_tasks",
        sa.Column("input_asset_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_generation_tasks_model_id", "generation_tasks", ["model_id"])
    op.create_index("ix_generation_tasks_input_asset_id", "generation_tasks", ["input_asset_id"])
    op.create_foreign_key(
        "fk_generation_tasks_model_id",
        "generation_tasks",
        "generation_models",
        ["model_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_generation_tasks_input_asset_id",
        "generation_tasks",
        "assets",
        ["input_asset_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_generation_tasks_input_asset_id", "generation_tasks", type_="foreignkey")
    op.drop_constraint("fk_generation_tasks_model_id", "generation_tasks", type_="foreignkey")
    op.drop_index("ix_generation_tasks_input_asset_id", table_name="generation_tasks")
    op.drop_index("ix_generation_tasks_model_id", table_name="generation_tasks")
    op.drop_column("generation_tasks", "input_asset_id")
    op.drop_column("generation_tasks", "model_code")
    op.drop_column("generation_tasks", "model_id")

    op.drop_index("ix_generation_models_deleted_at", table_name="generation_models")
    op.drop_index("ix_generation_models_is_default", table_name="generation_models")
    op.drop_index("ix_generation_models_status", table_name="generation_models")
    op.drop_index("ix_generation_models_provider", table_name="generation_models")
    op.drop_index("ix_generation_models_modality", table_name="generation_models")
    op.drop_index("ix_generation_models_code", table_name="generation_models")
    op.drop_table("generation_models")
