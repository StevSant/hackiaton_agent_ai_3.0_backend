"""Use case: aggregate potential savings analysis for amarillo + rojo claims.

Queries all non-verde claims, runs estimate_savings per row in Python,
sums totals, and groups results by tier level (nivel).

When no data exists, returns zeros and empty list — never fabricates.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.savings.calculator import estimate_savings
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.poliza import Poliza
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.reports import SavingsAnalysisOut, SavingsTierBucket

logger = logging.getLogger(__name__)

_TIERS_OF_INTEREST = ("amarillo", "rojo")


async def compute_savings_analysis(session: AsyncSession) -> SavingsAnalysisOut:
    """Return aggregated potential-savings figures for non-verde scored claims.

    Args:
        session: Live async SQLAlchemy session.

    Returns:
        SavingsAnalysisOut with totals and a per-nivel breakdown.
    """
    rows = (
        await session.execute(
            select(
                ClaimScore.score,
                ClaimScore.ml_probability,
                ClaimScore.tier,
                Siniestro.monto_reclamado,
                Siniestro.monto_pagado,
                Poliza.suma_asegurada,
                Poliza.deducible,
            )
            .join(Siniestro, ClaimScore.claim_id == Siniestro.id_siniestro)
            .join(Poliza, Siniestro.id_poliza == Poliza.id_poliza)
            .where(ClaimScore.tier.in_(_TIERS_OF_INTEREST))
        )
    ).all()

    # Per-nivel accumulators: {nivel: {casos, valor_en_riesgo, ahorro_potencial}}
    buckets: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"casos": 0, "valor_en_riesgo": 0.0, "ahorro_potencial": 0.0}
    )

    tasa = settings.TASA_RECUPERACION_AHORRO

    for row in rows:
        score: int = int(row[0])
        ml_prob: float | None = row[1]
        tier: str = str(row[2])
        monto_reclamado: float = float(row[3])
        monto_pagado: float = float(row[4]) if row[4] is not None else 0.0
        if row[5] is None:
            logger.warning(
                "compute_savings_analysis: skipping claim row — suma_asegurada is NULL "
                "(Poliza.suma_asegurada is non-nullable; this signals a data integrity issue)."
            )
            continue
        suma_asegurada: float = float(row[5])
        deducible: float = float(row[6]) if row[6] is not None else 0.0

        est = estimate_savings(
            monto_reclamado=monto_reclamado,
            suma_asegurada=suma_asegurada,
            monto_pagado=monto_pagado,
            deducible=deducible,
            score=score,
            ml_probability=ml_prob,
            tasa_recuperacion=tasa,
        )

        bucket = buckets[tier]
        bucket["casos"] = int(bucket["casos"]) + 1
        bucket["valor_en_riesgo"] = float(bucket["valor_en_riesgo"]) + est.valor_en_riesgo
        bucket["ahorro_potencial"] = (
            float(bucket["ahorro_potencial"]) + est.ahorro_potencial_estimado
        )

    por_nivel = [
        SavingsTierBucket(
            nivel=nivel,
            casos=int(b["casos"]),
            valor_en_riesgo=round(float(b["valor_en_riesgo"]), 2),
            ahorro_potencial=round(float(b["ahorro_potencial"]), 2),
        )
        for nivel, b in sorted(buckets.items(), key=lambda kv: kv[0])
    ]

    total_vr = round(sum(b.valor_en_riesgo for b in por_nivel), 2)
    total_ahorro = round(sum(b.ahorro_potencial for b in por_nivel), 2)
    total_casos = sum(b.casos for b in por_nivel)

    return SavingsAnalysisOut(
        total_valor_en_riesgo=total_vr,
        total_ahorro_potencial=total_ahorro,
        casos=total_casos,
        por_nivel=por_nivel,
    )
