"""Unit tests for the ORM metadata — no DB required.

These tests import Base + all models and assert that every expected table
exists with its key columns, plus that claim_narratives.embedding is a
384-dim Vector. They are the RED→GREEN anchor for Layer 1 (TDD).
"""

from sqlalchemy import inspect as sa_inspect

from app.infrastructure.db.base import Base
import app.infrastructure.db.models  # noqa: F401 — side-effect: registers all models


def _table(name: str):  # type: ignore[return]
    tables = Base.metadata.tables
    assert name in tables, f"Expected table '{name}' in metadata, got: {list(tables)}"
    return tables[name]


def _col(table, name: str):  # type: ignore[return]
    cols = {c.name: c for c in table.columns}
    assert name in cols, f"Expected column '{name}' in table '{table.name}', got: {list(cols)}"
    return cols[name]


# ── siniestros ──────────────────────────────────────────────────────────────

def test_siniestros_table_exists() -> None:
    _table("siniestros")


def test_siniestros_primary_key() -> None:
    t = _table("siniestros")
    _col(t, "id_siniestro")


def test_siniestros_core_columns() -> None:
    t = _table("siniestros")
    for col in [
        "id_poliza",
        "id_asegurado",
        "ramo",
        "cobertura",
        "fecha_ocurrencia",
        "fecha_reporte",
        "monto_reclamado",
        "monto_estimado",
        "monto_pagado",
        "estado",
        "sucursal",
        "descripcion",
        "documentos_completos",
        "beneficiario",
        "dias_desde_inicio_poliza",
        "dias_desde_fin_poliza",
        "dias_entre_ocurrencia_reporte",
        "historial_siniestros_asegurado",
        "etiqueta_fraude_simulada",
        "workspace_id",
    ]:
        _col(t, col)


# ── polizas ─────────────────────────────────────────────────────────────────

def test_polizas_table_exists() -> None:
    _table("polizas")


def test_polizas_primary_key() -> None:
    t = _table("polizas")
    _col(t, "id_poliza")


def test_polizas_core_columns() -> None:
    t = _table("polizas")
    for col in [
        "id_asegurado",
        "ramo",
        "fecha_inicio",
        "fecha_fin",
        "prima",
        "suma_asegurada",
        "deducible",
        "canal_venta",
        "ciudad",
        "estado_poliza",
    ]:
        _col(t, col)


# ── asegurados ───────────────────────────────────────────────────────────────

def test_asegurados_table_exists() -> None:
    _table("asegurados")


def test_asegurados_primary_key() -> None:
    t = _table("asegurados")
    _col(t, "id_asegurado")


def test_asegurados_core_columns() -> None:
    t = _table("asegurados")
    for col in [
        "segmento",
        "antiguedad",
        "ciudad",
        "num_polizas",
        "reclamos_ultimos_12_meses",
        "mora_actual",
        "score_cliente_simulado",
    ]:
        _col(t, col)


# ── beneficiarios_proveedores ─────────────────────────────────────────────────

def test_proveedores_table_exists() -> None:
    _table("beneficiarios_proveedores")


def test_proveedores_primary_key() -> None:
    t = _table("beneficiarios_proveedores")
    _col(t, "id_proveedor")


def test_proveedores_core_columns() -> None:
    t = _table("beneficiarios_proveedores")
    for col in [
        "tipo",
        "ciudad",
        "reclamos_asociados",
        "monto_promedio_reclamado",
        "porcentaje_casos_observados",
        "antiguedad",
    ]:
        _col(t, col)


# ── documentos ───────────────────────────────────────────────────────────────

def test_documentos_table_exists() -> None:
    _table("documentos")


def test_documentos_primary_key() -> None:
    t = _table("documentos")
    _col(t, "id_documento")


def test_documentos_core_columns() -> None:
    t = _table("documentos")
    for col in [
        "id_siniestro",
        "tipo_documento",
        "entregado",
        "legible",
        "fecha_emision",
        "inconsistencia_detectada",
        "observacion",
        "storage_path",
        "filename",
        "content_type",
    ]:
        _col(t, col)


# ── claim_scores ──────────────────────────────────────────────────────────────

def test_claim_scores_table_exists() -> None:
    _table("claim_scores")


def test_claim_scores_columns() -> None:
    t = _table("claim_scores")
    for col in [
        "id",
        "claim_id",
        "score",
        "tier",
        "activations",
        "ml_probability",
        "ml_factors",
        "anomaly_score",
        "similar",
        "computed_at",
    ]:
        _col(t, col)


# ── claim_reviews ─────────────────────────────────────────────────────────────

def test_claim_reviews_table_exists() -> None:
    _table("claim_reviews")


def test_claim_reviews_columns() -> None:
    t = _table("claim_reviews")
    for col in [
        "claim_id",
        "status",
        "escalated_by",
        "escalated_at",
        "escalation_note",
        "assigned_to",
        "taken_at",
        "dictamen_outcome",
        "dictamen_justificacion",
        "dictaminado_by",
        "dictaminado_at",
        "bounce_count",
        "bounce_note",
        "closed_by",
        "closed_at",
        "closed_note",
        "created_at",
        "updated_at",
    ]:
        _col(t, col)


# ── claim_narratives ──────────────────────────────────────────────────────────

def test_claim_narratives_table_exists() -> None:
    _table("claim_narratives")


def test_claim_narratives_columns() -> None:
    t = _table("claim_narratives")
    for col in ["id", "claim_id", "content", "embedding", "created_at"]:
        _col(t, col)


def test_claim_narratives_embedding_is_vector_384() -> None:
    """Embedding column must be pgvector Vector(384) — matches EMBEDDINGS_DIM."""
    from pgvector.sqlalchemy import Vector

    t = _table("claim_narratives")
    col = _col(t, "embedding")
    assert isinstance(col.type, Vector), (
        f"claim_narratives.embedding must be Vector, got {type(col.type)}"
    )
    assert col.type.dim == 384, (
        f"Expected dim=384, got dim={col.type.dim}"
    )
