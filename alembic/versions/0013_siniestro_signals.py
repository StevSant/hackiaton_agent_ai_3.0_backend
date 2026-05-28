"""0013_siniestro_signals — store non-derivable input facts on each claim.

Adds a ``signals`` JSONB column to ``siniestros``. It carries the
investigator / NLP-provided ground-truth facts that cannot be derived from a
claim's dates, amounts, or related rows (impossible dynamics, no third-party
trace, evident falsification, cloned narrative, similarity score, frequency
overrides, restrictive-list flags …). ``build_rule_context_from_db`` overlays
these onto the derived context so ``score_claim`` computes a genuine score
instead of a hand-authored one.

Revision ID: 0013_siniestro_signals
Revises: 0012_audit_events
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_siniestro_signals"
down_revision: str | None = "0012_audit_events"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "siniestros",
        sa.Column(
            "signals",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("siniestros", "signals")
