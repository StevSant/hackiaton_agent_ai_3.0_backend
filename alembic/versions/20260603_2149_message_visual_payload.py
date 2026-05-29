"""message visual_payload — add nullable JSONB visual_payload to messages.

Persists the new AgentVisual list payload (Phase 1+). When set, the
conversation-replay use case prefers this over the legacy chart_payload.
chart_payload is left untouched for backward compatibility.

Revision ID: f6f17b33233e
Revises: 0022_rule_overrides
Create Date: 2026-06-03 21:49:16.901107+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f6f17b33233e"
down_revision: str | None = "0022_rule_overrides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("visual_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "visual_payload")
