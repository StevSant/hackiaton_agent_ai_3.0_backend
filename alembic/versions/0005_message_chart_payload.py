"""0005_message_chart_payload — add nullable JSONB chart_payload to messages.

Persists the agent's emitted ChartEvent payload (when present) so the chart
survives page reloads.

Revision ID: 0005_message_chart_payload
Revises: cc22cbf44cf3
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_message_chart_payload"
down_revision: str | None = "cc22cbf44cf3"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("chart_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "chart_payload")
