"""0015_claim_score_narrative_analysis — cache the NLP narrative read.

Adds a nullable ``narrative_analysis`` JSONB column to ``claim_scores`` to cache
the output of the NLP analyzer (entidades + narrativa_ilogica + incoherencias +
resumen_narrativa). Null until the analyzer has run for a claim; existing rows
are unaffected.

Revision ID: 0015_claim_score_narrative_analysis
Revises: 0014_siniestro_resumen_editado
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0015_claim_score_narrative_analysis"
down_revision: str | None = "0014_siniestro_resumen_editado"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "claim_scores",
        sa.Column("narrative_analysis", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("claim_scores", "narrative_analysis")
