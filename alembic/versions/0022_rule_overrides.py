"""0022_rule_overrides — persist editable rule config + the change log.

Two tables back the dashboard rule editor:
- ``rule_overrides`` — current runtime state per rule (paused flag + threshold
  overlay). Absent rows mean "run with config.yaml defaults".
- ``rule_changes`` — append-only audit history of every edit, powering the
  "Historial de cambios" modal across restarts.

Revision ID: 0022_rule_overrides
Revises: 0021_evento_fields
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0022_rule_overrides"
down_revision: str | None = "0021_evento_fields"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "rule_overrides",
        sa.Column("code", sa.String(length=16), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "thresholds",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("updated_by", sa.String(length=160), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "rule_changes",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=160), nullable=False),
        sa.Column("rule_code", sa.String(length=16), nullable=False),
        sa.Column("rule_name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("before_value", sa.Text(), nullable=True),
        sa.Column("after_value", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_rule_changes_ts", "rule_changes", ["ts"])
    op.create_index("ix_rule_changes_rule_code", "rule_changes", ["rule_code"])


def downgrade() -> None:
    op.drop_index("ix_rule_changes_rule_code", table_name="rule_changes")
    op.drop_index("ix_rule_changes_ts", table_name="rule_changes")
    op.drop_table("rule_changes")
    op.drop_table("rule_overrides")
