"""split the legacy task history that was grouped into one session

Revision ID: 20260723_0002
Revises: 20260723_0001
Create Date: 2026-07-23
"""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "20260723_0002"
down_revision: str | None = "20260723_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Repair databases that ran the first session migration.

    The initial backfill made one session per owner. Its timestamp signature
    (session timestamps exactly match the first/last task timestamps) lets us
    target only those imported sessions, without splitting sessions users have
    intentionally continued.
    """
    bind = op.get_bind()
    tasks = sa.table(
        "generation_tasks",
        sa.column("id", sa.String),
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

    imported_session_ids = bind.execute(
        sa.select(sessions.c.id)
        .join(tasks, tasks.c.creation_session_id == sessions.c.id)
        .group_by(sessions.c.id, sessions.c.created_at, sessions.c.updated_at)
        .having(sa.func.count(tasks.c.id) > 1)
        .having(sa.func.min(tasks.c.created_at) == sessions.c.created_at)
        .having(sa.func.max(tasks.c.updated_at) == sessions.c.updated_at)
    ).scalars()

    for session_id in imported_session_ids:
        task_rows = bind.execute(
            sa.select(tasks.c.id, tasks.c.created_at, tasks.c.updated_at)
            .where(tasks.c.creation_session_id == session_id)
            .order_by(tasks.c.created_at.asc(), tasks.c.id.asc())
        ).mappings().all()
        session = bind.execute(
            sa.select(sessions.c.user_id, sessions.c.visitor_id)
            .where(sessions.c.id == session_id)
        ).mappings().one()

        # Retain the original row for the first task; give every other
        # historical task a separate session.
        for task in task_rows[1:]:
            new_session_id = str(uuid4())
            bind.execute(
                sa.insert(sessions).values(
                    id=new_session_id,
                    created_at=task["created_at"],
                    updated_at=task["updated_at"],
                    user_id=session["user_id"],
                    visitor_id=session["visitor_id"],
                )
            )
            bind.execute(
                sa.update(tasks)
                .where(tasks.c.id == task["id"])
                .values(creation_session_id=new_session_id)
            )


def downgrade() -> None:
    # The original one-session-per-owner grouping cannot be safely recreated
    # after users have continued any of those sessions.
    pass
