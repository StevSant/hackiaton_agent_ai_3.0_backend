"""Pure mapping helpers: ClaimDetail ↔ ORM row dicts.

No I/O, no SQLAlchemy session — only data transformation so these functions
are unit-testable without a database. Where the source `ClaimDetail` lacks a
column (segmento, antiguedad, prima, deducible…), the helpers below derive a
stable value from the row's identifier so the same input always produces the
same output (idempotent re-ingest).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.core.city_coords import coords_for_claim
from app.infrastructure.db.models.asegurado import Asegurado
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.documento import Documento
from app.infrastructure.db.models.poliza import Poliza
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.claim import ClaimDetail, ClaimDocument, ClaimReview, ClaimVehicle
from app.schemas.risk import FactorContribution, SimilarClaim, Tier

_SEGMENTOS = ["Premium", "Corporativo", "Estándar", "Joven", "Senior"]
_CANALES = ["Sucursal", "Digital", "Broker", "Agente", "Telemarketing"]
# Lookup is normalised via _ramo_key so the dataset's mixed casing
# ("Vehículos" / "vehiculos" / "Vida" / "vida") all resolve correctly.
_PRIMA_RATIO_BY_RAMO = {
    "vehiculos": 0.075,
    "salud": 0.055,
    "vida": 0.025,
    "hogar": 0.045,
    "accidentes personales": 0.035,
    "transporte": 0.050,
    "incendio": 0.030,
}
_DEDUCIBLE_RATIO_BY_RAMO = {
    "vehiculos": 0.05,
    "salud": 0.02,
    "hogar": 0.03,
    "incendio": 0.04,
    "transporte": 0.04,
}
_FS11_CODE = "FS-11"


def _ramo_key(ramo: str) -> str:
    """Normalise a ramo string for case/accent-insensitive lookup."""
    return (
        ramo.lower()
        .replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u")
        .strip()
    )

# ---------------------------------------------------------------------------
# ClaimDetail → ORM objects
# ---------------------------------------------------------------------------


def claim_detail_to_asegurado(c: ClaimDetail) -> Asegurado:
    """Asegurado row with deterministic per-id synthetic attributes.

    num_polizas / reclamos_ultimos_12_meses are intentionally left at 0 — the
    post-ingest aggregation pass fills them from the actual related rows.
    """
    seed = c.asegurado_id
    return Asegurado(
        id_asegurado=c.asegurado_id,
        nombre=c.asegurado or None,
        segmento=_stable_pick(f"seg-{seed}", _SEGMENTOS),
        antiguedad=_stable_int(f"ant-{seed}", 6, 240),
        ciudad=c.ciudad,
        num_polizas=0,
        reclamos_ultimos_12_meses=0,
        mora_actual=_stable_bool(f"mora-{seed}", prob=0.08),
        score_cliente_simulado=round(_stable_float(f"score-{seed}", 0.30, 0.95), 3),
    )


def claim_detail_to_poliza(c: ClaimDetail) -> Poliza:
    """Poliza row with deterministic prima / deducible / canal_venta."""
    key = _ramo_key(c.ramo)
    prima = round(c.suma_asegurada * _PRIMA_RATIO_BY_RAMO.get(key, 0.06), 2)
    deducible = round(c.suma_asegurada * _DEDUCIBLE_RATIO_BY_RAMO.get(key, 0.0), 2)
    return Poliza(
        id_poliza=c.poliza,
        id_asegurado=c.asegurado_id,
        ramo=c.ramo,
        fecha_inicio=c.fecha_inicio_poliza or c.fecha_ocurrencia,
        fecha_fin=c.fecha_fin_poliza or c.fecha_ocurrencia,
        prima=prima,
        suma_asegurada=c.suma_asegurada,
        deducible=deducible,
        canal_venta=_stable_pick(f"canal-{c.poliza}", _CANALES),
        ciudad=c.ciudad,
        estado_poliza="vigente",
    )


def claim_detail_to_siniestro(
    c: ClaimDetail,
    *,
    workspace_id: UUID | None = None,
) -> Siniestro:
    """Map ClaimDetail → Siniestro ORM object with full §2.8 fields."""
    vehiculo = c.vehiculo
    estado_lower = c.estado.lower()
    if estado_lower == "pago total":
        pagado = round(c.monto_reclamado * 0.90, 2)
    elif estado_lower == "pago parcial":
        pagado = round(c.monto_reclamado * 0.45, 2)
    elif estado_lower == "anticipo":
        pagado = round(c.monto_reclamado * 0.25, 2)
    else:
        pagado = 0.0

    # Prefer coords already on the ClaimDetail; derive deterministically when
    # the source predates the field (e.g. older claims.json or hand-curated demo).
    lat = c.latitude
    lng = c.longitude
    if lat is None or lng is None:
        coords = coords_for_claim(c.id, c.sucursal or c.ciudad)
        if coords is not None:
            lat, lng = coords

    return Siniestro(
        id_siniestro=c.id,
        id_poliza=c.poliza,
        id_asegurado=c.asegurado_id,
        workspace_id=workspace_id,
        ramo=c.ramo,
        cobertura=c.cobertura,
        fecha_ocurrencia=c.fecha_ocurrencia,
        fecha_reporte=c.fecha_reporte,
        monto_reclamado=c.monto_reclamado,
        monto_estimado=round(c.monto_reclamado * 0.95, 2),
        monto_pagado=pagado,
        estado=c.estado,
        sucursal=c.sucursal,
        descripcion=c.descripcion,
        documentos_completos=not any(d.falta for d in c.documentos),
        beneficiario=proveedor_id_for(c.proveedor),
        dias_desde_inicio_poliza=_dias_desde_inicio(c),
        dias_desde_fin_poliza=_dias_desde_fin(c),
        dias_entre_ocurrencia_reporte=(c.fecha_reporte - c.fecha_ocurrencia).days,
        # historial_siniestros_asegurado is filled by the post-ingest aggregator
        historial_siniestros_asegurado=0,
        etiqueta_fraude_simulada=1 if c.nivel == Tier.rojo else 0,
        # vehicle attributes
        placa=vehiculo.placa if vehiculo else None,
        chasis=vehiculo.chasis if vehiculo else None,
        motor=None,
        marca=vehiculo.marca if vehiculo else None,
        modelo=vehiculo.modelo if vehiculo else None,
        anio=vehiculo.anio if vehiculo else None,
        # geo
        latitude=lat,
        longitude=lng,
    )


def claim_detail_to_documentos(c: ClaimDetail) -> list[Documento]:
    """Map ClaimDetail.documentos → list[Documento] ORM objects.

    fecha_emision is set for delivered docs (deterministic offset before
    fecha_ocurrencia). inconsistencia_detectada flips on the first delivered
    doc when the claim carries an FS-11 alert (so the audit trail in the DB
    matches the rule that fired).
    """
    has_fs11 = any(a.code == _FS11_CODE for a in c.alertas)
    flagged_inconsistencia = False
    rows: list[Documento] = []
    for idx, doc in enumerate(c.documentos):
        doc_id = f"{c.id}-DOC-{idx:03d}"
        entregado = doc.estado.lower() in {"entregado", "completo"}
        legible = entregado and not doc.falta
        fecha_emision = None
        observacion: str | None = None
        inconsistencia = False
        if entregado:
            offset_days = _stable_int(f"docfecha-{doc_id}", 7, 90)
            fecha_emision = c.fecha_ocurrencia - timedelta(days=offset_days)
            if has_fs11 and not flagged_inconsistencia:
                inconsistencia = True
                flagged_inconsistencia = True
                observacion = (
                    "Inconsistencia detectada — fecha de emisión incompatible "
                    "con el siniestro."
                )
        else:
            observacion = "Pendiente de entrega por parte del asegurado."
        rows.append(
            Documento(
                id_documento=doc_id,
                id_siniestro=c.id,
                tipo_documento=doc.tipo,
                entregado=entregado,
                legible=legible,
                fecha_emision=fecha_emision,
                inconsistencia_detectada=inconsistencia,
                observacion=observacion,
            )
        )
    return rows


def claim_detail_to_proveedor(c: ClaimDetail) -> Proveedor | None:
    """Map ClaimDetail.proveedor → Proveedor row, or None when absent.

    `nombre` carries the readable name. The aggregate columns (`reclamos_asociados`,
    `monto_promedio_reclamado`, `porcentaje_casos_observados`) are filled by the
    post-ingest aggregator from the actual `siniestros` rows.
    """
    if not c.proveedor:
        return None
    prov_id = _slugify_id(c.proveedor)
    return Proveedor(
        id_proveedor=prov_id,
        nombre=c.proveedor,
        tipo="Proveedor",
        ciudad=c.ciudad,
        reclamos_asociados=1,
        monto_promedio_reclamado=c.monto_reclamado,
        porcentaje_casos_observados=0.0,
        antiguedad=_stable_int(f"prov-ant-{prov_id}", 6, 180),
    )


def proveedor_id_for(nombre: str | None) -> str | None:
    """Public alias of the deterministic ID derivation — used by ingest+read paths."""
    if not nombre:
        return None
    return _slugify_id(nombre)


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
    proveedor: Proveedor | None = None,
    asegurado: Asegurado | None = None,
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
        asegurado=(
            asegurado.nombre
            if asegurado is not None and asegurado.nombre
            else f"Asegurado {sin.id_asegurado[-4:]}"
        ),
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
        proveedor=_proveedor_display(proveedor),
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


def _proveedor_display(p: Proveedor | None) -> str | None:
    if p is None:
        return None
    return p.nombre or p.id_proveedor


def _stable_hash(seed: str) -> int:
    return int(hashlib.md5(seed.encode()).hexdigest(), 16)  # noqa: S324  not crypto


def _stable_int(seed: str, lo: int, hi: int) -> int:
    return lo + (_stable_hash(seed) % (hi - lo + 1))


def _stable_pick(seed: str, items: list[str]) -> str:
    return items[_stable_hash(seed) % len(items)]


def _stable_float(seed: str, lo: float, hi: float) -> float:
    fraction = (_stable_hash(seed) % 10_000) / 10_000.0
    return lo + fraction * (hi - lo)


def _stable_bool(seed: str, *, prob: float) -> bool:
    return ((_stable_hash(seed) % 10_000) / 10_000.0) < prob
