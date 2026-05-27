"""Use case: compute the executive-insights bundle from real claim data.

Every field is derived from the live database:
- ``anomalies``: top-2 highest-scoring rojo claims, surfaced as critical/potential.
- ``regional_fraud``: rojo + amarillo counts grouped by ``sucursal`` (top 5).
- ``claim_type_slices``: percentage distribution by canonical ramo (see
  ``app.domain.ramos``); display labels come from ``data/config/ramo_labels.json``.
- ``total_claims_label``: real claim count, formatted as "12,4k" past 1000.
- ``hotspots`` / ``incidents``: aggregated + per-claim records for the map.
- ``quarterly_outlook``: ``None`` until a real forecast pipeline lands —
  the frontend hides the section rather than render hardcoded copy.

When the DB has no data, fields return empty arrays / null. We never fabricate.
A missing DB session is an error (raised by the caller via ``Depends``).
"""

from __future__ import annotations

from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ramos import label_for, normalize_ramo
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.insights import (
    AiAnomalyOut,
    ClaimTypeSliceOut,
    HotspotOut,
    IncidentOut,
    InsightsBundleOut,
    RegionalFraudPointOut,
)


def _format_total(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".", ",")
    return str(n)


def _slice_key(ramo: str) -> tuple[str, str]:
    """Map a raw ramo string to ``(canonical_key, display_label)`` for the donut."""
    canonical = normalize_ramo(ramo)
    return (canonical, label_for(canonical))


def _derive_anomalies(
    rojo_rows: list[tuple[str, str | None, int]],
) -> list[AiAnomalyOut]:
    """Build Anomalías cards from the top-scoring rojo claims.

    Each row is ``(id_siniestro, sucursal, score)``. We surface at most 2
    cards so the UI doesn't get crowded, and pick high-score reds because
    those are the real anomalies the rules engine + ML flagged together.
    Returns ``[]`` if no rojos exist — the frontend renders an empty state.
    """
    cards: list[AiAnomalyOut] = []
    for i, (claim_id, sucursal, score) in enumerate(rojo_rows[:2]):
        severity = "critical" if score >= 85 else "potential"
        suc = sucursal or "sucursal no asignada"
        cards.append(
            AiAnomalyOut(
                id=f"top-rojo-{i + 1}",
                title=f"Caso de alto riesgo · {claim_id}",
                description=(
                    f"Score {score}/100 — concentración de señales en {suc}. "
                    "Requiere revisión humana."
                ),
                severity=severity,
                confidence=float(score),
            )
        )
    return cards


async def compute_insights(session: AsyncSession) -> InsightsBundleOut:
    """Aggregate live insights from ``siniestros`` + ``claim_scores``."""
    total = (
        await session.execute(select(func.count(Siniestro.id_siniestro)))
    ).scalar() or 0

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
    ]

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
        ClaimTypeSliceOut(
            key=k,
            label=label,
            pct=round(count / total_ramos * 100, 1),
        )
        for k, (label, count) in sorted(bucketed.items(), key=lambda kv: -kv[1][1])
    ]

    rojo_rows = (
        await session.execute(
            select(
                Siniestro.id_siniestro,
                Siniestro.sucursal,
                ClaimScore.score,
            )
            .join(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .where(ClaimScore.tier == "rojo")
            .order_by(desc(ClaimScore.score))
            .limit(5)
        )
    ).all()
    anomalies = _derive_anomalies(
        [(row[0], row[1], int(row[2])) for row in rojo_rows]
    )

    hotspot_rows = (
        await session.execute(
            select(
                Siniestro.sucursal,
                func.count(Siniestro.id_siniestro),
                func.coalesce(
                    func.sum(
                        case(
                            (ClaimScore.tier.in_(["amarillo", "rojo"]), 1),
                            else_=0,
                        )
                    ),
                    0,
                ),
                func.coalesce(func.avg(ClaimScore.score), 0.0),
            )
            .outerjoin(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .where(Siniestro.sucursal.isnot(None))
            .group_by(Siniestro.sucursal)
            .order_by(desc(func.count(Siniestro.id_siniestro)))
        )
    ).all()
    hotspots = [
        HotspotOut(
            sucursal=row[0],
            count=int(row[1]),
            alertas=int(row[2]),
            avg_score=float(row[3]),
        )
        for row in hotspot_rows
    ]

    incident_rows = (
        await session.execute(
            select(
                Siniestro.id_siniestro,
                Siniestro.sucursal,
                Siniestro.fecha_ocurrencia,
                func.coalesce(ClaimScore.score, 0),
                func.coalesce(ClaimScore.tier, "verde"),
            )
            .outerjoin(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .where(Siniestro.sucursal.isnot(None))
        )
    ).all()
    incidents = [
        IncidentOut(
            id_siniestro=row[0],
            sucursal=row[1],
            score=int(row[3] or 0),
            tier=str(row[4] or "verde"),
            fecha_ocurrencia=row[2].isoformat() if row[2] else None,
        )
        for row in incident_rows
    ]

    return InsightsBundleOut(
        anomalies=anomalies,
        regional_fraud=regional_fraud,
        claim_type_slices=slices,
        total_claims_label=_format_total(int(total)),
        quarterly_outlook=None,
        hotspots=hotspots,
        incidents=incidents,
    )
