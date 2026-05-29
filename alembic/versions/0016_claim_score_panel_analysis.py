"""0016_claim_score_panel_analysis — cache the multi-agent panel debate.

Adds a nullable ``panel_analysis`` JSONB column to ``claim_scores`` to cache the
output of the fraud-analysis panel (lanes + moderator_text + consensus +
generated_at). Advisory only — never affects the score. Null until a panel run
has completed for a claim; existing rows are unaffected.

Revision ID: 0016_claim_score_panel_analysis
Revises: 0015_claim_score_narrative_analysis
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0016_claim_score_panel_analysis"
down_revision: str | None = "0015_claim_score_narrative_analysis"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "claim_scores",
        sa.Column("panel_analysis", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("claim_scores", "panel_analysis")
