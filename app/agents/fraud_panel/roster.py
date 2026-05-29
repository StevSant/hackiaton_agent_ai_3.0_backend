"""The fixed 4-specialist roster + their data-slice extractors.

Each slice_fn pulls only the part of the ClaimDetail that specialist reasons
over, so its prompt stays focused and its token cost low.
"""

from __future__ import annotations

from typing import Any

from app.agents.fraud_panel.specialist import Specialist
from app.schemas.claim import ClaimDetail


def claim_header(c: ClaimDetail) -> dict[str, Any]:
    """Shared case facts every specialist sees on top of its focused slice.

    Each lens otherwise reasons blind to montos, fechas and policy proximity —
    this grounds all four in the same core context without leaking the other
    lenses' signals.
    """
    header: dict[str, Any] = {
        "id": c.id,
        "ramo": c.ramo,
        "cobertura": c.cobertura,
        "estado": c.estado,
        "monto_reclamado": c.monto_reclamado,
        "monto_estimado": c.monto_estimado,
        "suma_asegurada": c.suma_asegurada,
        "fecha_ocurrencia": c.fecha_ocurrencia,
        "fecha_reporte": c.fecha_reporte,
        "fecha_inicio_poliza": c.fecha_inicio_poliza,
        "fecha_fin_poliza": c.fecha_fin_poliza,
    }
    if c.fecha_inicio_poliza is not None:
        header["dias_desde_inicio_poliza"] = (c.fecha_ocurrencia - c.fecha_inicio_poliza).days
    if c.vehiculo is not None:
        header["vehiculo"] = {
            "marca": c.vehiculo.marca,
            "modelo": c.vehiculo.modelo,
            "anio": c.vehiculo.anio,
        }
    return header


def _slice_reglas(c: ClaimDetail) -> dict[str, Any]:
    return {
        "score": c.score,
        "nivel": c.nivel.value,
        "alertas": [
            {"code": a.code, "puntos": a.puntos, "detalle": a.detalle} for a in c.alertas
        ],
    }


def _slice_ml(c: ClaimDetail) -> dict[str, Any]:
    return {
        "ml_probability": c.ml_probability,
        "ml_factors": [
            {"feature": f.feature, "shap_value": f.shap_value, "direction": f.direction}
            for f in c.ml_factors
        ],
        "anomaly_score": c.anomaly_score,
    }


def _slice_narrativa(c: ClaimDetail) -> dict[str, Any]:
    return {
        "descripcion": c.descripcion,
        "similar": [
            {"claim_id": s.claim_id, "similarity": s.similarity, "snippet": s.snippet}
            for s in c.similar
        ],
    }


def _slice_documentos_red(c: ClaimDetail) -> dict[str, Any]:
    return {
        "documentos": [
            {"tipo": d.tipo, "estado": d.estado, "falta": d.falta} for d in c.documentos
        ],
        "proveedor": c.proveedor,
    }


PANEL_ROSTER: list[Specialist] = [
    Specialist("reglas", "Analista de Reglas", "reglas", "especialista_reglas", _slice_reglas),
    Specialist("ml", "Analista de ML/Anomalía", "ml", "especialista_ml", _slice_ml),
    Specialist(
        "narrativa",
        "Analista de Narrativa",
        "narrativa",
        "especialista_narrativa",
        _slice_narrativa,
    ),
    Specialist(
        "documentos_red",
        "Analista de Documentos/Red",
        "documentos_red",
        "especialista_documentos_red",
        _slice_documentos_red,
    ),
]

MODERATOR_PROMPT_ID = "moderador"
