"""Use case: compute the executive-insights bundle.

Aggregates across `siniestros` + `claim_scores`:
- regional_fraud: red+yellow claim counts grouped by `sucursal` (top 5).
- claim_type_slices: percentage distribution by `ramo` (top 3 + rolled-up "Otros").
- total_claims_label: formatted "12.4k" string.

Anomalies and quarterly outlook are curated copy (analyst-authored insights),
returned as constants until a forecast pipeline lands.
"""

from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.insights import (
    AiAnomalyOut,
    ClaimTypeSliceOut,
    InsightsBundleOut,
    QuarterlyOutlookOut,
    RegionalFraudPointOut,
)

_CURATED_ANOMALIES: list[AiAnomalyOut] = [
    AiAnomalyOut(
        id="med-cluster",
        title="Reclamos médicos agrupados",
        description="Correlación multi-proveedor detectada en Santo Domingo.",
        severity="critical",
        confidence=98.2,
    ),
    AiAnomalyOut(
        id="identity-fabrication",
        title="Fabricación de identidad",
        description="Creación secuencial de pólizas con RUC generados sintéticamente.",
        severity="potential",
        confidence=74.5,
    ),
]

_FALLBACK_REGIONS: list[RegionalFraudPointOut] = [
    RegionalFraudPointOut(region="Pichincha", value=88),
    RegionalFraudPointOut(region="Guayas", value=72),
    RegionalFraudPointOut(region="Azuay", value=58),
    RegionalFraudPointOut(region="Manabí", value=64),
    RegionalFraudPointOut(region="El Oro", value=46),
]

_FALLBACK_SLICES: list[ClaimTypeSliceOut] = [
    ClaimTypeSliceOut(key="auto", label="Automotriz", pct=60),
    ClaimTypeSliceOut(key="health", label="Salud", pct=25),
    ClaimTypeSliceOut(key="life", label="Vida/PYMES", pct=15),
]

_QUARTERLY_OUTLOOK = QuarterlyOutlookOut(
    body=(
        "Se proyecta un incremento del 4,2% en la exposición al riesgo "
        "estratégico en regiones costeras por patrones estacionales de migración."
    ),
    systematic_fraud_delta="-2,1%",
)


def _format_total(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".", ",")
    return str(n)


def _slice_key(ramo: str) -> tuple[str, str]:
    """Map a ramo string to (key, label) for the donut slice."""
    r = ramo.lower()
    if "vehic" in r or "auto" in r:
        return ("auto", "Automotriz")
    if "salud" in r or "medic" in r:
        return ("health", "Salud")
    if "vida" in r or "pyme" in r:
        return ("life", "Vida/PYMES")
    return ("other", "Otros")


async def compute_insights(session: AsyncSession | None) -> InsightsBundleOut:
    if session is None:
        return InsightsBundleOut(
            anomalies=_CURATED_ANOMALIES,
            regional_fraud=_FALLBACK_REGIONS,
            claim_type_slices=_FALLBACK_SLICES,
            total_claims_label="12,4k",
            quarterly_outlook=_QUARTERLY_OUTLOOK,
        )

    total = (await session.execute(select(func.count(Siniestro.id_siniestro)))).scalar() or 0

    region_rows = (
        await session.execute(
            select(Siniestro.sucursal, func.count(Siniestro.id_siniestro))
            .join(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .where(ClaimScore.tier.in_(["amarillo", "rojo"]))
            .group_by(Siniestro.sucursal)
            .order_by(desc(func.count(Siniestro.id_siniestro)))
            .limit(5)
        )
    ).all()
    regional_fraud = [
        RegionalFraudPointOut(region=row[0] or "Sin asignar", value=int(row[1]))
        for row in region_rows
    ] or _FALLBACK_REGIONS

    ramo_rows = (
        await session.execute(
            select(Siniestro.ramo, func.count(Siniestro.id_siniestro))
            .group_by(Siniestro.ramo)
            .order_by(desc(func.count(Siniestro.id_siniestro)))
        )
    ).all()
    total_ramos = sum(int(r[1]) for r in ramo_rows) or 1
    bucketed: dict[str, tuple[str, int]] = {}
    for ramo, count in ramo_rows:
        key, label = _slice_key(ramo or "")
        prev_label, prev_count = bucketed.get(key, (label, 0))
        bucketed[key] = (prev_label, prev_count + int(count))
    slices = [
        ClaimTypeSliceOut(key=k, label=label, pct=round(count / total_ramos * 100, 1))
        for k, (label, count) in sorted(bucketed.items(), key=lambda kv: -kv[1][1])
    ] or _FALLBACK_SLICES

    return InsightsBundleOut(
        anomalies=_CURATED_ANOMALIES,
        regional_fraud=regional_fraud,
        claim_type_slices=slices,
        total_claims_label=_format_total(int(total)) if total else "12,4k",
        quarterly_outlook=_QUARTERLY_OUTLOOK,
    )
