"""Build one ``ClaimDetail`` + ``RuleContext`` pair from a ``ClaimArchetype``.

The resulting ``ClaimDetail`` already has a fully-populated ``RuleContext`` so
that score_claim produces meaningful, tier-spanning results without a database.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any

from app.core.city_coords import coords_for_claim
from app.domain.ramos import normalize_ramo
from app.domain.rules.context import RuleContext
from app.schemas.claim import (
    ClaimAlert,
    ClaimDetail,
    ClaimDocument,
    ClaimReview,
    ClaimTimelineEvent,
    ClaimVehicle,
    ReviewStatus,
)
from app.schemas.risk import Tier
from app.use_cases.generate_dataset._archetypes import ClaimArchetype
from app.use_cases.generate_dataset._pools import (
    APELLIDOS,
    CODE_PROVIDER_PATTERNS,
    MARCAS_VEHICULO,
    MODELOS_VEHICULO,
    NOMBRES_FEMENINOS,
    NOMBRES_MASCULINOS,
    PROVEEDOR_PREFIJOS,
    PROVEEDOR_QUALIFIERS,
    PROVEEDORES_DEFAULT,
    PROVEEDORES_GENERALES,
    PROVEEDORES_HOGAR,
    PROVEEDORES_SALUD,
    RAMOS_VEHICULO,
    SUCURSALES,
)

# Default proveedor pool per canonical ramo. "vida" intentionally omitted —
# life-insurance claims use beneficiarios, not proveedores; archetypes that need
# a service provider (funeraria, médico legal) pin one explicitly.
_PROVEEDOR_POOL_BY_CANONICAL: dict[str, list[str]] = {
    "vehiculos": PROVEEDORES_DEFAULT,
    "salud": PROVEEDORES_SALUD,
    "hogar": PROVEEDORES_HOGAR,
    "generales": PROVEEDORES_GENERALES,
}

# Reference date for offset calculations
_REF_DATE = date(2026, 5, 26)


def _stable_int(seed: str, lo: int, hi: int) -> int:
    """Deterministic int in [lo, hi] derived from a string seed."""
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)  # noqa: S324 — not crypto
    return lo + (h % (hi - lo + 1))


def _stable_pick(seed: str, items: list[str]) -> str:
    return items[_stable_int(seed, 0, len(items) - 1)]


def _ecuador_full_name(idx: int) -> str:
    """Deterministic plausible Ecuadorian full name for the asegurado at index ``idx``.

    Pattern: ``<nombre> <apellido_paterno> <apellido_materno>``. Gender is also
    derived from ``idx`` so the first name pool matches.
    """
    gender = _stable_int(f"ase-gender-{idx}", 0, 1)
    pool = NOMBRES_MASCULINOS if gender == 0 else NOMBRES_FEMENINOS
    nombre = _stable_pick(f"ase-nombre-{idx}", pool)
    apellido1 = _stable_pick(f"ase-ap1-{idx}", APELLIDOS)
    apellido2 = _stable_pick(f"ase-ap2-{idx}", APELLIDOS)
    return f"{nombre} {apellido1} {apellido2}"


def _ecuador_provider_name(idx: int) -> str:
    """Deterministic plausible Ecuadorian business name for a provider.

    Used as a fallback when an archetype doesn't pin an explicit ``proveedor``
    string. The result is a `<prefijo> <qualifier>` combination — e.g.
    "Taller Mecánico Cumbayá" or "Carrocerías del Pacífico".
    """
    prefijo = _stable_pick(f"prov-prefijo-{idx}", PROVEEDOR_PREFIJOS)
    qualifier = _stable_pick(f"prov-qualifier-{idx}", PROVEEDOR_QUALIFIERS)
    return f"{prefijo} {qualifier}"


def _looks_like_code(value: str) -> bool:
    upper = value.upper()
    return any(upper.startswith(p) for p in CODE_PROVIDER_PATTERNS)


def _make_vehicle(archetype: ClaimArchetype, idx: int) -> ClaimVehicle | None:
    if archetype.ramo not in RAMOS_VEHICULO:
        return None
    marca = _stable_pick(f"marca-{idx}", MARCAS_VEHICULO)
    modelo = _stable_pick(f"modelo-{idx}", MODELOS_VEHICULO)
    # Ecuador tiene un parque automotor antiguo: ampliamos el rango a 2010
    anio = _stable_int(f"anio-{idx}", 2010, 2024)
    # Ecuadorian plates: first letter is a province code (A, B, C, E, G, H, I,
    # K, L, M, N, O, P, Q, R, S, T, U, V, W, X, Y, Z — D/F/J not used).
    province_codes = "ABCEGHIKLMNOPQRSTUVWXYZ"
    first = province_codes[_stable_int(f"pl-{idx}-0", 0, len(province_codes) - 1)]
    rest = "".join(
        chr(65 + _stable_int(f"pl-{idx}-{i}", 0, 25)) for i in (1, 2)
    )
    digits = "".join(str(_stable_int(f"pd-{idx}-{i}", 0, 9)) for i in range(4))
    placa = f"{first}{rest}-{digits}"
    chasis_raw = hashlib.sha1(f"chasis-{idx}".encode()).hexdigest()[:17].upper()  # noqa: S324
    return ClaimVehicle(
        marca=marca,
        modelo=modelo,
        anio=anio,
        placa=placa,
        chasis=chasis_raw,
    )


def _make_docs(
    archetype: ClaimArchetype, idx: int
) -> list[ClaimDocument]:
    base_docs = [
        ClaimDocument(tipo="Cédula de identidad", estado="Entregado"),
        ClaimDocument(tipo="Matrícula vehicular", estado="Entregado"),
    ]
    for doc_tipo in archetype.docs_faltantes:
        base_docs.append(ClaimDocument(tipo=doc_tipo, estado="Pendiente", falta=True))
    if not archetype.docs_faltantes:
        base_docs.append(ClaimDocument(tipo="Denuncia policial", estado="Entregado"))
    return base_docs


def _make_timeline(
    fecha_ocurrencia: date,
    fecha_reporte: date,
    nivel: Tier,
) -> list[ClaimTimelineEvent]:
    tone_map = {Tier.verde: "ok", Tier.amarillo: "warn", Tier.rojo: "danger"}
    tone = tone_map[nivel]
    events = [
        ClaimTimelineEvent(
            date=str(fecha_ocurrencia),
            title="Ocurrencia",
            tone=tone,
        )
    ]
    if fecha_reporte > fecha_ocurrencia:
        events.append(
            ClaimTimelineEvent(
                date=str(fecha_reporte),
                title="Reporte",
                tone=tone,
                desc=f"{(fecha_reporte - fecha_ocurrencia).days} días después",
            )
        )
    return events


def build_claim(archetype: ClaimArchetype, idx: int) -> tuple[ClaimDetail, RuleContext]:
    """Return a ``(ClaimDetail, RuleContext)`` pair for the given archetype."""
    fecha_ocurrencia = _REF_DATE - timedelta(days=archetype.fecha_ocurrencia_offset)
    fecha_reporte = fecha_ocurrencia + timedelta(days=archetype.reporte_delay_days)

    # Derive policy dates so fecha_inicio_poliza is consistent with dias_desde_inicio_poliza.
    # When the archetype has an explicit dias value, set fecha_inicio = fecha_ocurrencia - dias.
    # This ensures PATCH /claims/{id} + RuleContext.from_claim() re-fires FS-01/RF-05.
    dias_inicio = archetype.dias_desde_inicio_poliza
    _inicio_offset = dias_inicio if dias_inicio is not None else 180
    # always a concrete date — never None — used as base for fin calculation below
    fecha_inicio_poliza: date = fecha_ocurrencia - timedelta(days=_inicio_offset)
    fecha_fin_poliza: date = fecha_inicio_poliza + timedelta(days=365)

    monto_reclamado = round(archetype.suma_asegurada * archetype.monto_ratio, 2)

    # Stable but unique IDs — no real PII
    claim_id = f"SIN-{idx:04d}"
    asegurado_hash = hashlib.sha1(f"ase-{idx}".encode()).hexdigest()[:8].upper()  # noqa: S324
    asegurado_id = f"ASE-{asegurado_hash}"
    poliza_id = f"POL-{idx:04d}"
    asegurado_name = _ecuador_full_name(idx)

    # Archetype-pinned provider wins; otherwise pick from the curated pool for
    # the claim's canonical ramo (vehiculos / salud / hogar / generales). Vida
    # claims keep proveedor=None unless the archetype pins one. Codes that
    # accidentally look like internal IDs are replaced with a procedural
    # Ecuadorian business name so we never emit "PROV-OBS-XXX" as a display nombre.
    proveedor = archetype.proveedor
    if proveedor is None:
        canonical = normalize_ramo(archetype.ramo)
        pool = _PROVEEDOR_POOL_BY_CANONICAL.get(canonical)
        if pool:
            proveedor = _stable_pick(f"prov-{idx}", pool)
    if proveedor is not None and _looks_like_code(proveedor):
        proveedor = _ecuador_provider_name(idx)
    sucursal = SUCURSALES.get(archetype.ciudad, archetype.ciudad)
    coords = coords_for_claim(claim_id, sucursal, ramo=archetype.ramo)
    lat = coords[0] if coords else None
    lng = coords[1] if coords else None
    vehiculo = _make_vehicle(archetype, idx)
    documentos = _make_docs(archetype, idx)

    # Compute monto_vs_suma_pct from the actual values
    monto_vs_suma_pct = (
        monto_reclamado / archetype.suma_asegurada
        if archetype.suma_asegurada > 0
        else 0.0
    )

    ctx = RuleContext(
        dias_entre_ocurrencia_reporte=archetype.reporte_delay_days,
        dias_desde_inicio_poliza=(
            archetype.dias_desde_inicio_poliza
            if archetype.dias_desde_inicio_poliza is not None
            else 9999
        ),
        historial_siniestros_asegurado=(
            archetype.historial_siniestros_asegurado
            if archetype.historial_siniestros_asegurado is not None
            else 0
        ),
        frecuencia_vehiculo=(
            archetype.frecuencia_vehiculo
            if archetype.frecuencia_vehiculo is not None
            else 0
        ),
        frecuencia_conductor=(
            archetype.frecuencia_conductor
            if archetype.frecuencia_conductor is not None
            else 0
        ),
        eventos_rc_previos=(
            archetype.eventos_rc_previos
            if archetype.eventos_rc_previos is not None
            else 0
        ),
        proveedor_en_lista_restrictiva=archetype.proveedor_en_lista_restrictiva,
        beneficiario_en_lista_restrictiva=archetype.beneficiario_en_lista_restrictiva,
        proveedor_casos_observados=archetype.proveedor_casos_observados,
        documentos_incompletos=archetype.documentos_incompletos,
        inconsistencia_documental=archetype.inconsistencia_documental,
        falsificacion_evidente=archetype.falsificacion_evidente,
        narrativa_similar_score=archetype.narrativa_similar_score,
        narrativa_clonada=archetype.narrativa_clonada,
        dinamica_imposible=archetype.dinamica_imposible,
        sin_rastro_tercero=archetype.sin_rastro_tercero,
        evento_medianoche=archetype.evento_medianoche,
        monto_vs_suma_pct=monto_vs_suma_pct,
        monto_vs_reparacion_avg_pct=archetype.monto_vs_reparacion_avg_pct,
        es_robo=archetype.es_robo,
        es_cobertura_ptxrb=archetype.es_cobertura_ptxrb,
        demora_denuncia_horas=archetype.demora_denuncia_horas,
        cobertura_rc=archetype.cobertura_rc,
        narrativa_ilógica=archetype.narrativa_ilógica,
    )

    # Pre-score via rules engine — bake result into ClaimDetail
    from app.domain.rules.aggregator import aggregate  # local import avoids cycle
    from app.domain.rules.catalog import all_rules, get_meta
    from app.schemas.risk import RuleActivation

    activations: list[RuleActivation] = []
    # Build a minimal ClaimDetail first (score/nivel/alertas are placeholders)
    partial = ClaimDetail(
        id=claim_id,
        ramo=archetype.ramo,
        cobertura=archetype.cobertura,
        asegurado=asegurado_name,
        asegurado_id=asegurado_id,
        poliza=poliza_id,
        ciudad=archetype.ciudad,
        fecha_ocurrencia=fecha_ocurrencia,
        fecha_reporte=fecha_reporte,
        fecha_inicio_poliza=fecha_inicio_poliza,
        fecha_fin_poliza=fecha_fin_poliza,
        monto_reclamado=monto_reclamado,
        suma_asegurada=archetype.suma_asegurada,
        estado=archetype.estado,
        sucursal=sucursal,
        vehiculo=vehiculo,
        proveedor=proveedor,
        descripcion=archetype.descripcion or f"Siniestro sintético {claim_id}.",
        score=0,
        nivel=Tier.verde,
        alertas=[],
        timeline=[],
        documentos=documentos,
        review=ClaimReview(status=ReviewStatus.pendiente),
        latitude=lat,
        longitude=lng,
    )

    for rule in all_rules():
        result = rule.evaluate(partial, ctx)
        if result is not None:
            activations.append(result)

    score, tier = aggregate(activations)

    # Project activations → ClaimAlert
    alertas: list[ClaimAlert] = []
    _sev: dict[str, str] = {"rojo": "high", "amarillo": "med", "verde": "low"}
    for act in activations:
        meta = get_meta(act.code)
        detalle = meta.short_description if meta is not None else act.code
        alertas.append(
            ClaimAlert(
                code=act.code,
                puntos=act.points,
                severidad=_sev.get(act.tier_hint.value, "low"),
                detalle=detalle,
            )
        )

    timeline = _make_timeline(fecha_ocurrencia, fecha_reporte, tier)

    claim = partial.model_copy(
        update={
            "score": score,
            "nivel": tier,
            "alertas": alertas,
            "timeline": timeline,
        }
    )
    return claim, ctx


def claim_to_row(claim: ClaimDetail) -> dict[str, Any]:
    """Return a dict representing a ``siniestros`` table row (§2.8 schema)."""
    coords = coords_for_claim(claim.id, claim.sucursal or claim.ciudad, ramo=claim.ramo)
    lat, lng = coords if coords is not None else ("", "")
    return {
        "id_siniestro": claim.id,
        "id_poliza": claim.poliza,
        "id_asegurado": claim.asegurado_id,
        "ramo": claim.ramo,
        "cobertura": claim.cobertura,
        "fecha_ocurrencia": str(claim.fecha_ocurrencia),
        "fecha_reporte": str(claim.fecha_reporte),
        "monto_reclamado": claim.monto_reclamado,
        "monto_estimado": round(claim.monto_reclamado * 0.95, 2),
        "monto_pagado": (
            round(claim.monto_reclamado * 0.90, 2)
            if claim.estado == "Pago Total"
            else 0.0
        ),
        "estado": claim.estado,
        "sucursal": claim.sucursal,
        "descripcion": claim.descripcion,
        "documentos_completos": "no" if any(d.falta for d in claim.documentos) else "sí",
        "beneficiario": "",
        "fecha_inicio_poliza": str(claim.fecha_inicio_poliza) if claim.fecha_inicio_poliza else "",
        "fecha_fin_poliza": str(claim.fecha_fin_poliza) if claim.fecha_fin_poliza else "",
        "dias_desde_inicio_poliza": (
            (claim.fecha_ocurrencia - claim.fecha_inicio_poliza).days
            if claim.fecha_inicio_poliza else ""
        ),
        "dias_desde_fin_poliza": (
            (claim.fecha_fin_poliza - claim.fecha_ocurrencia).days
            if claim.fecha_fin_poliza else ""
        ),
        "dias_entre_ocurrencia_reporte": (
            (claim.fecha_reporte - claim.fecha_ocurrencia).days
        ),
        "historial_siniestros_asegurado": 0,
        "etiqueta_fraude_simulada": 1 if claim.nivel == Tier.rojo else 0,
        "latitude": lat,
        "longitude": lng,
    }
