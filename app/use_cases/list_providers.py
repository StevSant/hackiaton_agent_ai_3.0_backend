"""Use case: list providers with per-provider metrics.

Aggregates `siniestros` (count, monto) and `claim_scores` (alertas = yellow/red
tiers) grouped by `Siniestro.beneficiario` joined back to `Proveedor.id_proveedor`.
The database is the sole source of truth — there is no in-memory fallback.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.network import ProviderOut

_RESTRICTIVE_THRESHOLD = 0.5


def _display_name(p: Proveedor) -> str:
    return p.nombre or f"{p.tipo} {p.id_proveedor}"


async def list_providers(session: AsyncSession) -> list[ProviderOut]:
    proveedores = (await session.execute(select(Proveedor))).scalars().all()
    results: list[ProviderOut] = []
    for p in proveedores:
        casos_row = (
            await session.execute(
                select(
                    func.count(Siniestro.id_siniestro),
                    func.coalesce(func.sum(Siniestro.monto_reclamado), 0.0),
                ).where(Siniestro.beneficiario == p.id_proveedor)
            )
        ).one()
        casos = int(casos_row[0] or 0)
        monto = float(casos_row[1] or 0.0)

        alertas = (
            await session.execute(
                select(func.count())
                .select_from(Siniestro)
                .join(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
                .where(
                    Siniestro.beneficiario == p.id_proveedor,
                    ClaimScore.tier.in_(["amarillo", "rojo"]),
                )
            )
        ).scalar() or 0

        if casos == 0:
            casos = p.reclamos_asociados
            monto = p.monto_promedio_reclamado * max(p.reclamos_asociados, 1)

        results.append(
            ProviderOut(
                id_proveedor=p.id_proveedor,
                nombre=_display_name(p),
                tipo=p.tipo,
                ciudad=p.ciudad,
                casos=casos,
                alertas=int(alertas),
                monto=monto,
                lista_restrictiva=p.porcentaje_casos_observados >= _RESTRICTIVE_THRESHOLD,
            )
        )

    results.sort(key=lambda r: (r.alertas, r.casos), reverse=True)
    return results
