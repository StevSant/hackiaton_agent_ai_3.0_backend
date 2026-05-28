"""0007_claim_reviews_names — denormalize display names on claim_reviews.

Revision ID: 0007_claim_reviews_names
Revises: 0006_asegurado_nombre
Create Date: 2026-05-28

Adds four nullable name columns to `claim_reviews` so the analyst histórico /
antifraude inbox can render human-readable labels without joining the auth
users table at read time. Names are denormalized at action time, so historical
rows survive subsequent user renames.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0007_claim_reviews_names"
down_revision: str | None = "0006_asegurado_nombre"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "claim_reviews",
        sa.Column("escalated_by_name", sa.String(128), nullable=True),
    )
    op.add_column(
        "claim_reviews",
        sa.Column("assigned_to_name", sa.String(128), nullable=True),
    )
    op.add_column(
        "claim_reviews",
        sa.Column("dictaminado_by_name", sa.String(128), nullable=True),
    )
    op.add_column(
        "claim_reviews",
        sa.Column("closed_by_name", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("claim_reviews", "closed_by_name")
    op.drop_column("claim_reviews", "dictaminado_by_name")
    op.drop_column("claim_reviews", "assigned_to_name")
    op.drop_column("claim_reviews", "escalated_by_name")
