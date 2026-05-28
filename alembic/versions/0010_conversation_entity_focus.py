"""0010_conversation_entity_focus — add context_provider_id / context_asegurado_id to conversations.

Enables the "Ask AI from provider / asegurado detail pages" feature (spec
2026-05-28-entity-ask-ai-design.md §4.2). The single-focus invariant is
enforced at the wire level — only one of the three context_* columns may be
non-null per row.

Revision ID: 0010_conversation_entity_focus
Revises: 0009_msg_transparency
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0010_conversation_entity_focus"
down_revision: str | None = "0009_msg_transparency"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("context_provider_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("context_asegurado_id", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "context_asegurado_id")
    op.drop_column("conversations", "context_provider_id")
