"""0001_initial — create all Layer-1 tables + pgvector extension + HNSW index.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # Enable pgvector (idempotent — safe to run multiple times).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── asegurados ──────────────────────────────────────────────────────────
    op.create_table(
        "asegurados",
        sa.Column("id_asegurado", sa.String(64), nullable=False),
        sa.Column("segmento", sa.String(80), nullable=True),
        sa.Column("antiguedad", sa.Integer(), nullable=True),
        sa.Column("ciudad", sa.String(100), nullable=False),
        sa.Column("num_polizas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reclamos_ultimos_12_meses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mora_actual", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("score_cliente_simulado", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id_asegurado", name="pk_asegurados"),
    )

    # ── polizas ─────────────────────────────────────────────────────────────
    op.create_table(
        "polizas",
        sa.Column("id_poliza", sa.String(64), nullable=False),
        sa.Column("id_asegurado", sa.String(64), nullable=False),
        sa.Column("ramo", sa.String(120), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.Column("prima", sa.Float(), nullable=False),
        sa.Column("suma_asegurada", sa.Float(), nullable=False),
        sa.Column("deducible", sa.Float(), nullable=False, server_default="0"),
        sa.Column("canal_venta", sa.String(80), nullable=True),
        sa.Column("ciudad", sa.String(100), nullable=False),
        sa.Column("estado_poliza", sa.String(60), nullable=False),
        sa.ForeignKeyConstraint(
            ["id_asegurado"],
            ["asegurados.id_asegurado"],
            name="fk_polizas_id_asegurado_asegurados",
        ),
        sa.PrimaryKeyConstraint("id_poliza", name="pk_polizas"),
    )
    op.create_index("ix_polizas_id_asegurado", "polizas", ["id_asegurado"])

    # ── siniestros ───────────────────────────────────────────────────────────
    op.create_table(
        "siniestros",
        sa.Column("id_siniestro", sa.String(64), nullable=False),
        sa.Column("id_poliza", sa.String(64), nullable=False),
        sa.Column("id_asegurado", sa.String(64), nullable=False),
        sa.Column("ramo", sa.String(120), nullable=False),
        sa.Column("cobertura", sa.String(120), nullable=False),
        sa.Column("fecha_ocurrencia", sa.Date(), nullable=False),
        sa.Column("fecha_reporte", sa.Date(), nullable=False),
        sa.Column("monto_reclamado", sa.Float(), nullable=False),
        sa.Column("monto_estimado", sa.Float(), nullable=True),
        sa.Column("monto_pagado", sa.Float(), nullable=True),
        sa.Column("estado", sa.String(60), nullable=False),
        sa.Column("sucursal", sa.String(120), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("documentos_completos", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("beneficiario", sa.String(128), nullable=True),
        sa.Column("dias_desde_inicio_poliza", sa.Integer(), nullable=True),
        sa.Column("dias_desde_fin_poliza", sa.Integer(), nullable=True),
        sa.Column("dias_entre_ocurrencia_reporte", sa.Integer(), nullable=True),
        sa.Column("historial_siniestros_asegurado", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("etiqueta_fraude_simulada", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("placa", sa.String(20), nullable=True),
        sa.Column("chasis", sa.String(40), nullable=True),
        sa.Column("motor", sa.String(40), nullable=True),
        sa.Column("marca", sa.String(80), nullable=True),
        sa.Column("modelo", sa.String(80), nullable=True),
        sa.Column("anio", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["id_poliza"],
            ["polizas.id_poliza"],
            name="fk_siniestros_id_poliza_polizas",
        ),
        sa.ForeignKeyConstraint(
            ["id_asegurado"],
            ["asegurados.id_asegurado"],
            name="fk_siniestros_id_asegurado_asegurados",
        ),
        sa.PrimaryKeyConstraint("id_siniestro", name="pk_siniestros"),
    )
    op.create_index("ix_siniestros_id_poliza", "siniestros", ["id_poliza"])
    op.create_index("ix_siniestros_id_asegurado", "siniestros", ["id_asegurado"])

    # ── beneficiarios_proveedores ────────────────────────────────────────────
    op.create_table(
        "beneficiarios_proveedores",
        sa.Column("id_proveedor", sa.String(64), nullable=False),
        sa.Column("tipo", sa.String(80), nullable=False),
        sa.Column("ciudad", sa.String(100), nullable=False),
        sa.Column("reclamos_asociados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("monto_promedio_reclamado", sa.Float(), nullable=False, server_default="0"),
        sa.Column("porcentaje_casos_observados", sa.Float(), nullable=False, server_default="0"),
        sa.Column("antiguedad", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id_proveedor", name="pk_beneficiarios_proveedores"),
    )

    # ── documentos ───────────────────────────────────────────────────────────
    op.create_table(
        "documentos",
        sa.Column("id_documento", sa.String(64), nullable=False),
        sa.Column("id_siniestro", sa.String(64), nullable=False),
        sa.Column("tipo_documento", sa.String(120), nullable=False),
        sa.Column("entregado", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("legible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("fecha_emision", sa.Date(), nullable=True),
        sa.Column("inconsistencia_detectada", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["id_siniestro"],
            ["siniestros.id_siniestro"],
            name="fk_documentos_id_siniestro_siniestros",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id_documento", name="pk_documentos"),
    )
    op.create_index("ix_documentos_id_siniestro", "documentos", ["id_siniestro"])

    # ── claim_scores ─────────────────────────────────────────────────────────
    op.create_table(
        "claim_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("claim_id", sa.String(64), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("activations", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("ml_probability", sa.Float(), nullable=True),
        sa.Column("ml_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("anomaly_score", sa.Float(), nullable=True),
        sa.Column("similar", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["siniestros.id_siniestro"],
            name="fk_claim_scores_claim_id_siniestros",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_claim_scores"),
        sa.UniqueConstraint("claim_id", name="uq_claim_scores_claim_id"),
    )
    op.create_index("ix_claim_scores_claim_id", "claim_scores", ["claim_id"])

    # ── claim_reviews ─────────────────────────────────────────────────────────
    op.create_table(
        "claim_reviews",
        sa.Column("claim_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="pendiente"),
        sa.Column("escalated_by", sa.String(128), nullable=True),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalation_note", sa.Text(), nullable=True),
        sa.Column("assigned_to", sa.String(128), nullable=True),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dictamen_outcome", sa.String(40), nullable=True),
        sa.Column("dictamen_justificacion", sa.Text(), nullable=True),
        sa.Column("dictaminado_by", sa.String(128), nullable=True),
        sa.Column("dictaminado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bounce_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bounce_note", sa.Text(), nullable=True),
        sa.Column("closed_by", sa.String(128), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["siniestros.id_siniestro"],
            name="fk_claim_reviews_claim_id_siniestros",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("claim_id", name="pk_claim_reviews"),
    )
    op.create_index("ix_claim_reviews_status", "claim_reviews", ["status"])

    # ── claim_narratives ──────────────────────────────────────────────────────
    op.create_table(
        "claim_narratives",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("claim_id", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["claim_id"],
            ["siniestros.id_siniestro"],
            name="fk_claim_narratives_claim_id_siniestros",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_claim_narratives"),
    )
    op.create_index("ix_claim_narratives_claim_id", "claim_narratives", ["claim_id"])
    # HNSW cosine index for pgvector nearest-neighbour search (FS-13).
    op.execute(
        "CREATE INDEX ix_claim_narratives_embedding_hnsw "
        "ON claim_narratives USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("claim_narratives")
    op.drop_table("claim_reviews")
    op.drop_table("claim_scores")
    op.drop_table("documentos")
    op.drop_table("beneficiarios_proveedores")
    op.drop_table("siniestros")
    op.drop_table("polizas")
    op.drop_table("asegurados")
    op.execute("DROP EXTENSION IF EXISTS vector")
