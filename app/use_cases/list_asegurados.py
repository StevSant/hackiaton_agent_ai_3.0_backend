"""Use case: list asegurados (insured persons) with per-person metrics.

Aggregates `siniestros` (count, monto) and `claim_scores` (alertas = yellow/red
tiers) grouped by `Siniestro.id_asegurado` joined back to `Asegurado.id_asegurado`.
The database is the sole source of truth — there is no in-memory fallback.

Issued as a single grouped query so 400+ asegurados don't translate into 1000+
round-trips against the Supabase pooler.
"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ramos import normalize_ramo
from app.infrastructure.db.models.asegurado import Asegurado
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.asegurados import AseguradoOut


def _display_name(a: Asegurado) -> str:
    return a.nombre or f"Asegurado {a.id_asegurado[-4:]}"


async def list_asegurados(session: AsyncSession) -> list[AseguradoOut]:
    alerta_case = case(
        (ClaimScore.tier.in_(["amarillo", "rojo"]), 1),
        else_=0,
    )
    aggregate_stmt = (
        select(
            Siniestro.id_asegurado.label("ase_id"),
            func.count(Siniestro.id_siniestro).label("casos"),
            func.coalesce(func.sum(Siniestro.monto_reclamado), 0.0).label("monto"),
            func.coalesce(func.sum(alerta_case), 0).label("alertas"),
            func.array_agg(func.distinct(Siniestro.ramo)).label("ramos"),
        )
        .select_from(Siniestro)
        .outerjoin(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
        .group_by(Siniestro.id_asegurado)
    )
    rows = (await session.execute(aggregate_stmt)).all()

    aggregates: dict[str, tuple[int, float, int, list[str]]] = {}
    for row in rows:
        ase_id, casos, monto, alertas, ramos = row
        ramos_list = [r for r in (ramos or []) if r]
        aggregates[ase_id] = (
            int(casos or 0),
            float(monto or 0.0),
            int(alertas or 0),
            ramos_list,
        )

    asegurados = (await session.execute(select(Asegurado))).scalars().all()
    results: list[AseguradoOut] = []
    for a in asegurados:
        casos, monto, alertas, raw_ramos = aggregates.get(
            a.id_asegurado, (0, 0.0, 0, [])
        )
        ramos = sorted({normalize_ramo(r) for r in raw_ramos})
        results.append(
            AseguradoOut(
                id_asegurado=a.id_asegurado,
                nombre=_display_name(a),
                segmento=a.segmento,
                ciudad=a.ciudad,
                antiguedad=a.antiguedad,
                num_polizas=a.num_polizas,
                reclamos_ultimos_12_meses=a.reclamos_ultimos_12_meses,
                mora_actual=a.mora_actual,
                score_cliente_simulado=a.score_cliente_simulado,
                casos=casos,
                alertas=alertas,
                monto=monto,
                ramos=ramos,
            )
        )

    results.sort(key=lambda r: (r.alertas, r.casos), reverse=True)
    return results
