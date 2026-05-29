"""0021_evento_fields — add ground-truth columns from the evento v2 dataset.

Adds 7 nullable columns that are populated by `scripts/import_evento_dataset.py`
and preferred by the rules engine over the existing heuristics when not None:

  beneficiarios_proveedores:
    - en_lista_restrictiva  BOOLEAN  (RF-03 + FS-07 prefer over porcentaje heuristic)
    - motivo_restriccion    VARCHAR  (evidence field for RF-03)

  asegurados:
    - reclamos_historico_total   INTEGER  (total lifetime claims)
    - reclamos_rc_sin_tercero    INTEGER  (FS-06 RC-only events, ground truth)
    - perfil_riesgo              VARCHAR  (display label: Alto / Medio / Bajo)

  siniestros:
    - numero_parte_policial  VARCHAR  (police report number — audit trail)
    - similitud_narrativa_max FLOAT   (FS-13 precomputed score 0-1; fallback to pgvector)

All columns are NULLABLE — existing rows are unaffected.
CRITICAL: revision id ≤ 20 chars so alembic_version.version_num (varchar) fits.

Revision ID: 0021_evento_fields
Revises:     0016_claim_score_panel_analysis
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0021_evento_fields"
down_revision: str | None = "0016_claim_score_panel_analysis"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # beneficiarios_proveedores — restrictive-list ground truth
    op.add_column(
        "beneficiarios_proveedores",
        sa.Column("en_lista_restrictiva", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "beneficiarios_proveedores",
        sa.Column("motivo_restriccion", sa.String(255), nullable=True),
    )

    # asegurados — richer frequency + risk profile
    op.add_column(
        "asegurados",
        sa.Column("reclamos_historico_total", sa.Integer(), nullable=True),
    )
    op.add_column(
        "asegurados",
        sa.Column("reclamos_rc_sin_tercero", sa.Integer(), nullable=True),
    )
    op.add_column(
        "asegurados",
        sa.Column("perfil_riesgo", sa.String(80), nullable=True),
    )

    # siniestros — police report + precomputed narrative similarity
    op.add_column(
        "siniestros",
        sa.Column("numero_parte_policial", sa.String(80), nullable=True),
    )
    op.add_column(
        "siniestros",
        sa.Column("similitud_narrativa_max", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("siniestros", "similitud_narrativa_max")
    op.drop_column("siniestros", "numero_parte_policial")
    op.drop_column("asegurados", "perfil_riesgo")
    op.drop_column("asegurados", "reclamos_rc_sin_tercero")
    op.drop_column("asegurados", "reclamos_historico_total")
    op.drop_column("beneficiarios_proveedores", "motivo_restriccion")
    op.drop_column("beneficiarios_proveedores", "en_lista_restrictiva")
