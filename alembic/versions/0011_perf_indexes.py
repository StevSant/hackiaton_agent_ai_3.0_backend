"""0011_perf_indexes — hot-column indexes for triage + agent paths.

Adds indexes that the audit (perf overhaul 2026-05-28) identified as turning
sequential scans into index range scans for the dashboard listing, the rules
catalog, and the agent's aggregate / missing-docs / executive-summary tools.

Revision ID: 0011_perf_indexes
Revises: 0010_conversation_entity_focus
Create Date: 2026-05-28
"""

from __future__ import annotations

from alembic import op

revision: str = "0011_perf_indexes"
down_revision: str | None = "0010_conversation_entity_focus"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # claim_scores hot paths: tier filter + score DESC sort
    op.create_index(
        "ix_claim_scores_tier",
        "claim_scores",
        ["tier"],
    )
    op.create_index(
        "ix_claim_scores_tier_score_desc",
        "claim_scores",
        ["tier", "score"],
        postgresql_ops={"score": "DESC"},
    )
    op.create_index(
        "ix_claim_scores_computed_at",
        "claim_scores",
        ["computed_at"],
    )
    # GIN on activations powers the rules-catalog GROUP BY (jsonb_array_elements
    # + ->> are NOT GIN-accelerated, but the @> path tests we may want later
    # are. Cheap to keep.)
    op.create_index(
        "ix_claim_scores_activations_gin",
        "claim_scores",
        ["activations"],
        postgresql_using="gin",
    )

    # siniestros listing filters
    op.create_index(
        "ix_siniestros_fecha_ocurrencia",
        "siniestros",
        ["fecha_ocurrencia"],
    )
    op.create_index(
        "ix_siniestros_beneficiario",
        "siniestros",
        ["beneficiario"],
    )


def downgrade() -> None:
    op.drop_index("ix_siniestros_beneficiario", table_name="siniestros")
    op.drop_index("ix_siniestros_fecha_ocurrencia", table_name="siniestros")
    op.drop_index("ix_claim_scores_activations_gin", table_name="claim_scores")
    op.drop_index("ix_claim_scores_computed_at", table_name="claim_scores")
    op.drop_index("ix_claim_scores_tier_score_desc", table_name="claim_scores")
    op.drop_index("ix_claim_scores_tier", table_name="claim_scores")
