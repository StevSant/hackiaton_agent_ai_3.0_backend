"""Pure mapping helpers: ClaimDetail ↔ ORM row dicts.

No I/O, no SQLAlchemy session — only data transformation so these functions
are unit-testable without a database.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.infrastructure.db.models.asegurado import Asegurado
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.documento import Documento
from app.infrastructure.db.models.poliza import Poliza
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.claim import ClaimDetail, ClaimDocument, ClaimReview, ClaimVehicle
from app.schemas.risk import FactorContribution, SimilarClaim, Tier

# ---------------------------------------------------------------------------
# ClaimDetail → ORM objects
# ---------------------------------------------------------------------------


def claim_detail_to_asegurado(c: ClaimDetail) -> Asegurado:
    """Minimal Asegurado row from claim fields (upsert-safe: PK only required)."""
    return Asegurado(
        id_asegurado=c.asegurado_id,
        ciudad=c.ciudad,
        # population-level defaults; will be overwritten when the full asegurado
        # dataset is loaded separately
        num_polizas=0,
        reclamos_ultimos_12_meses=0,
        mora_actual=False,
    )


def claim_detail_to_poliza(c: ClaimDetail) -> Poliza:
    """Minimal Poliza row derived from claim fields (upsert-safe)."""
    return Poliza(
        id_poliza=c.poliza,
        id_asegurado=c.asegurado_id,
        ramo=c.ramo,
        fecha_inicio=c.fecha_inicio_poliza or c.fecha_ocurrencia,
        fecha_fin=c.fecha_fin_poliza or c.fecha_ocurrencia,
        prima=0.0,
        suma_asegurada=c.suma_asegurada,
        deducible=0.0,
        ciudad=c.ciudad,
        estado_poliza="vigente",
    )


def claim_detail_to_siniestro(c: ClaimDetail) -> Siniestro:
    """Map ClaimDetail → Siniestro ORM object."""
    vehiculo = c.vehiculo
    return Siniestro(
        id_siniestro=c.id,
        id_poliza=c.poliza,
        id_asegurado=c.asegurado_id,
        ramo=c.ramo,
        cobertura=c.cobertura,
        fecha_ocurrencia=c.fecha_ocurrencia,
        fecha_reporte=c.fecha_reporte,
        monto_reclamado=c.monto_reclamado,
        monto_estimado=None,
        monto_pagado=None,
        estado=c.estado,
        sucursal=c.sucursal,
        descripcion=c.descripcion,
        documentos_completos=not any(d.falta for d in c.documentos),
        beneficiario=None,
        dias_desde_inicio_poliza=_dias_desde_inicio(c),
        dias_desde_fin_poliza=_dias_desde_fin(c),
        dias_entre_ocurrencia_reporte=(c.fecha_reporte - c.fecha_ocurrencia).days,
        historial_siniestros_asegurado=0,
        etiqueta_fraude_simulada=0,
        # vehicle attributes
        placa=vehiculo.placa if vehiculo else None,
        chasis=vehiculo.chasis if vehiculo else None,
        motor=None,
        marca=vehiculo.marca if vehiculo else None,
        modelo=vehiculo.modelo if vehiculo else None,
        anio=vehiculo.anio if vehiculo else None,
    )


def claim_detail_to_documentos(c: ClaimDetail) -> list[Documento]:
    """Map ClaimDetail.documentos → list[Documento] ORM objects."""
    rows: list[Documento] = []
    for idx, doc in enumerate(c.documentos):
        # Deterministic ID: claim_id + position so re-ingestion is idempotent.
        doc_id = f"{c.id}-DOC-{idx:03d}"
        rows.append(
            Documento(
                id_documento=doc_id,
                id_siniestro=c.id,
                tipo_documento=doc.tipo,
                entregado=doc.estado.lower() in {"entregado", "completo"},
                legible=not doc.falta,
                fecha_emision=None,
                inconsistencia_detectada=False,
                observacion=None,
            )
        )
    return rows


def claim_detail_to_proveedor(c: ClaimDetail) -> Proveedor | None:
    """Map ClaimDetail.proveedor → Proveedor row, or None when absent."""
    if not c.proveedor:
        return None
    # Use the proveedor name as ID (stable, deterministic)
    prov_id = _slugify_id(c.proveedor)
    return Proveedor(
        id_proveedor=prov_id,
        tipo="Proveedor",
        ciudad=c.ciudad,
        reclamos_asociados=1,
        monto_promedio_reclamado=c.monto_reclamado,
        porcentaje_casos_observados=0.0,
    )


def claim_detail_to_score(c: ClaimDetail) -> ClaimScore:
    """Map ClaimDetail scoring fields → ClaimScore ORM object."""
    activations_json: list[dict[str, Any]] = [
        {
            "code": a.code,
            "puntos": a.puntos,
            "severidad": a.severidad,
            "detalle": a.detalle,
        }
        for a in c.alertas
    ]
    ml_factors_json: list[dict[str, Any]] = [
        {
            "feature": f.feature,
            "shap_value": f.shap_value,
            "direction": f.direction,
        }
        for f in c.ml_factors
    ]
    similar_json: list[dict[str, Any]] = [
        {
            "claim_id": s.claim_id,
            "similarity": s.similarity,
            "snippet": s.snippet,
        }
        for s in c.similar
    ]
    return ClaimScore(
        claim_id=c.id,
        score=c.score,
        tier=c.nivel.value,
        activations=activations_json,
        ml_probability=None,
        ml_factors=ml_factors_json,
        anomaly_score=c.anomaly_score,
        similar=similar_json,
        computed_at=datetime.now(tz=UTC),
    )


# ---------------------------------------------------------------------------
# ORM rows → ClaimDetail
# ---------------------------------------------------------------------------


def rows_to_claim_detail(
    sin: Siniestro,
    pol: Poliza | None,
    score_row: ClaimScore | None,
    documentos: list[Documento],
) -> ClaimDetail:
    """Assemble a ClaimDetail from ORM row objects (no DB I/O here)."""
    tier = Tier(score_row.tier) if score_row else Tier.verde
    score_val = score_row.score if score_row else 0

    alertas_raw: list[dict[str, Any]] = score_row.activations if score_row else []
    from app.schemas.claim import ClaimAlert  # local to avoid circular at module level

    alertas = [
        ClaimAlert(
            code=a["code"],
            puntos=a["puntos"],
            severidad=a["severidad"],
            detalle=a["detalle"],
        )
        for a in alertas_raw
    ]

    ml_factors = [
        FactorContribution(
            feature=f["feature"],
            shap_value=f["shap_value"],
            direction=f["direction"],
        )
        for f in (score_row.ml_factors if score_row else [])
    ]

    similar = [
        SimilarClaim(
            claim_id=s["claim_id"],
            similarity=s["similarity"],
            snippet=s["snippet"],
        )
        for s in (score_row.similar if score_row else [])
    ]

    vehiculo: ClaimVehicle | None = None
    if sin.marca and sin.modelo and sin.anio and sin.placa:
        vehiculo = ClaimVehicle(
            marca=sin.marca,
            modelo=sin.modelo,
            anio=sin.anio,
            placa=sin.placa,
            chasis=sin.chasis,
        )

    docs = [
        ClaimDocument(
            tipo=d.tipo_documento,
            estado="Entregado" if d.entregado else "Pendiente",
            falta=not d.entregado,
        )
        for d in documentos
    ]

    return ClaimDetail(
        id=sin.id_siniestro,
        ramo=sin.ramo,
        cobertura=sin.cobertura,
        asegurado=f"Asegurado {sin.id_asegurado[-4:]}",
        asegurado_id=sin.id_asegurado,
        poliza=sin.id_poliza,
        ciudad=pol.ciudad if pol else "",
        fecha_ocurrencia=sin.fecha_ocurrencia,
        fecha_reporte=sin.fecha_reporte,
        fecha_inicio_poliza=pol.fecha_inicio if pol else None,
        fecha_fin_poliza=pol.fecha_fin if pol else None,
        monto_reclamado=sin.monto_reclamado,
        suma_asegurada=pol.suma_asegurada if pol else 0.0,
        estado=sin.estado,
        sucursal=sin.sucursal,
        vehiculo=vehiculo,
        proveedor=None,  # not stored relationally on siniestro; populated via JOIN if needed
        descripcion=sin.descripcion,
        score=score_val,
        nivel=tier,
        alertas=alertas,
        timeline=[],
        documentos=docs,
        review=ClaimReview(),
        ml_factors=ml_factors,
        similar=similar,
        anomaly_score=score_row.anomaly_score if score_row else None,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _dias_desde_inicio(c: ClaimDetail) -> int | None:
    if c.fecha_inicio_poliza is None:
        return None
    return (c.fecha_ocurrencia - c.fecha_inicio_poliza).days


def _dias_desde_fin(c: ClaimDetail) -> int | None:
    if c.fecha_fin_poliza is None:
        return None
    return (c.fecha_fin_poliza - c.fecha_ocurrencia).days


def _slugify_id(name: str) -> str:
    """Stable deterministic ID from a string (UUID5 with URL namespace)."""
    return f"PROV-{uuid.uuid5(uuid.NAMESPACE_URL, name).hex[:8].upper()}"
