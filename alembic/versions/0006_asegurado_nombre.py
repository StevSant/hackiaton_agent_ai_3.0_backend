"""0006_asegurado_nombre — add `nombre` column to `asegurados`.

Revision ID: 0006_asegurado_nombre
Revises: 0005_message_chart_payload
Create Date: 2026-05-27

Adds a human-readable display name for the insured person. The original
ingest mapping dropped the name from ClaimDetail and the UI rendered a
placeholder ("Asegurado 3981"). This column lets the loader persist the
real Ecuadorian name produced by the generator so analysts see meaningful
labels instead of placeholders.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0006_asegurado_nombre"
down_revision: str | None = "0005_message_chart_payload"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "asegurados",
        sa.Column("nombre", sa.String(160), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("asegurados", "nombre")
