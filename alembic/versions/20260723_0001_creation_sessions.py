"""add durable creation sessions

Revision ID: 20260723_0001
Revises: 20260722_0001
Create Date: 2026-07-23
"""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_0001"
down_revision: str | None = "20260722_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creation_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("visitor_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["visitor_id"], ["anonymous_visitors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_creation_sessions_user_id", "creation_sessions", ["user_id"])
    op.create_index("ix_creation_sessions_visitor_id", "creation_sessions", ["visitor_id"])
    op.create_index(
        "ix_creation_sessions_user_updated",
        "creation_sessions",
        ["user_id", "updated_at"],
    )
    op.create_index(
        "ix_creation_sessions_visitor_updated",
        "creation_sessions",
        ["visitor_id", "updated_at"],
    )

    op.add_column(
        "generation_tasks",
        sa.Column("creation_session_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_generation_tasks_creation_session_id",
        "generation_tasks",
        ["creation_session_id"],
    )
    op.create_foreign_key(
        "fk_generation_tasks_creation_session_id",
        "generation_tasks",
        "creation_sessions",
        ["creation_session_id"],
        ["id"],
    )

    # Sessions did not exist before this migration. Preserve the original
    # semantics: each historical top-level task becomes its own session.
    bind = op.get_bind()
    tasks = sa.table(
        "generation_tasks",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("visitor_id", sa.String),
        sa.column("creation_session_id", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    sessions = sa.table(
        "creation_sessions",
        sa.column("id", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("user_id", sa.String),
        sa.column("visitor_id", sa.String),
    )

    legacy_tasks = bind.execute(
        sa.select(
            tasks.c.id,
            tasks.c.user_id,
            tasks.c.visitor_id,
            tasks.c.created_at,
            tasks.c.updated_at,
        ).where(tasks.c.creation_session_id.is_(None))
    ).mappings()
    for task in legacy_tasks:
        user_id = task["user_id"]
        visitor_id = None if user_id else task["visitor_id"]
        if user_id is None and visitor_id is None:
            continue
        session_id = str(uuid4())
        bind.execute(
            sa.insert(sessions).values(
                id=session_id,
                created_at=task["created_at"],
                updated_at=task["updated_at"],
                user_id=user_id,
                visitor_id=visitor_id,
            )
        )
        bind.execute(
            sa.update(tasks)
            .where(tasks.c.id == task["id"])
            .values(creation_session_id=session_id)
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_generation_tasks_creation_session_id",
        "generation_tasks",
        type_="foreignkey",
    )
    op.drop_index("ix_generation_tasks_creation_session_id", table_name="generation_tasks")
    op.drop_column("generation_tasks", "creation_session_id")

    op.drop_index("ix_creation_sessions_visitor_updated", table_name="creation_sessions")
    op.drop_index("ix_creation_sessions_user_updated", table_name="creation_sessions")
    op.drop_index("ix_creation_sessions_visitor_id", table_name="creation_sessions")
    op.drop_index("ix_creation_sessions_user_id", table_name="creation_sessions")
    op.drop_table("creation_sessions")
