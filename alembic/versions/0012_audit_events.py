"""0012_audit_events — persist the analyst + system activity log.

The audit log was in-memory only (``InMemoryAuditStore``), so it reset on every
process restart / ``--reload`` and the Auditoría page always showed 0 events.
This table backs ``DbAuditStore`` so audit history survives restarts.

Revision ID: 0012_audit_events
Revises: 0011_perf_indexes
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0012_audit_events"
down_revision: str | None = "0011_perf_indexes"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=20), nullable=False),
        sa.Column("actor_name", sa.String(length=160), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("target", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_events_ts", "audit_events", ["ts"])
    op.create_index("ix_audit_events_actor", "audit_events", ["actor"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_target", "audit_events", ["target"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_target", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_actor", table_name="audit_events")
    op.drop_index("ix_audit_events_ts", table_name="audit_events")
    op.drop_table("audit_events")
