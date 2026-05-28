"""0009_message_transparency_metadata — add transparency_metadata JSONB to messages.

Persists the agent's reasoning steps, tool calls/results, and citations so
the explainability UI (transparency cards) survives page reloads. Without this
column, `GET /conversations/{id}` returned only the final text — the 25%-grade
explainability bucket was invisible on history load.

Revision ID: 0009_message_transparency_metadata
Revises: 0008_claim_reviews_names
Create Date: 2026-05-28

Column contract:
  NULL     → user message or legacy assistant message (pre-migration)
  {}       → assistant message with no recorded transparency (safe fallback)
  { steps, tool_calls, citations }  → full transparency payload
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009_msg_transparency"
down_revision: str | None = "0008_claim_reviews_names"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "transparency_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("messages", "transparency_metadata")
