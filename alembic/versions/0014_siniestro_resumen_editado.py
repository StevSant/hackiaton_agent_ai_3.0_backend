"""0014_siniestro_resumen_editado — analyst-editable case summary.

Adds a ``resumen_editado`` Text column to ``siniestros``.  Analysts can
save an edited version of the AI-generated case summary; the column stores
that override.  Nullable so all existing rows are unaffected.

Revision ID: 0014_siniestro_resumen_editado
Revises: 0013_siniestro_signals
Create Date: 2026-05-28
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0014_siniestro_resumen_editado"
down_revision: str | None = "0013_siniestro_signals"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column("siniestros", sa.Column("resumen_editado", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("siniestros", "resumen_editado")
