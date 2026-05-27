"""Use case: list providers with per-provider metrics.

Aggregates `siniestros` (count, monto) and `claim_scores` (alertas = yellow/red
tiers) grouped by `Siniestro.beneficiario` joined back to `Proveedor.id_proveedor`.
The database is the sole source of truth — there is no in-memory fallback.

Issued as a single grouped query so 57 providers don't translate to 170+
round-trips against the Supabase pooler.
"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ramos import normalize_ramo
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.network import ProviderOut

_RESTRICTIVE_THRESHOLD = 0.5


def _display_name(p: Proveedor) -> str:
    return p.nombre or f"{p.tipo} {p.id_proveedor}"


async def list_providers(session: AsyncSession) -> list[ProviderOut]:
    alerta_case = case(
        (ClaimScore.tier.in_(["amarillo", "rojo"]), 1),
        else_=0,
    )
    aggregate_stmt = (
        select(
            Siniestro.beneficiario.label("prov_id"),
            func.count(Siniestro.id_siniestro).label("casos"),
            func.coalesce(func.sum(Siniestro.monto_reclamado), 0.0).label("monto"),
            func.coalesce(func.sum(alerta_case), 0).label("alertas"),
            func.array_agg(func.distinct(Siniestro.ramo)).label("ramos"),
        )
        .select_from(Siniestro)
        .outerjoin(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
        .where(Siniestro.beneficiario.is_not(None))
        .group_by(Siniestro.beneficiario)
    )
    rows = (await session.execute(aggregate_stmt)).all()

    aggregates: dict[str, tuple[int, float, int, list[str]]] = {}
    for row in rows:
        prov_id, casos, monto, alertas, ramos = row
        ramos_list = [r for r in (ramos or []) if r]
        aggregates[prov_id] = (int(casos or 0), float(monto or 0.0), int(alertas or 0), ramos_list)

    proveedores = (await session.execute(select(Proveedor))).scalars().all()
    results: list[ProviderOut] = []
    for p in proveedores:
        casos, monto, alertas, raw_ramos = aggregates.get(p.id_proveedor, (0, 0.0, 0, []))
        if casos == 0:
            casos = p.reclamos_asociados
            monto = p.monto_promedio_reclamado * max(p.reclamos_asociados, 1)
        ramos = sorted({normalize_ramo(r) for r in raw_ramos})
        results.append(
            ProviderOut(
                id_proveedor=p.id_proveedor,
                nombre=_display_name(p),
                tipo=p.tipo,
                ciudad=p.ciudad,
                casos=casos,
                alertas=alertas,
                monto=monto,
                lista_restrictiva=p.porcentaje_casos_observados >= _RESTRICTIVE_THRESHOLD,
                ramos=ramos,
            )
        )

    results.sort(key=lambda r: (r.alertas, r.casos), reverse=True)
    return results
