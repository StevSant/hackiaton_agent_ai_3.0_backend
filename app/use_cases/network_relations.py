"""Use case: build the provider↔insured relationship graph.

Each `Siniestro` links a provider (`beneficiario` == `Proveedor.id_proveedor`)
to an insured (`id_asegurado`). Grouping claims by that pair yields a bipartite
graph: provider nodes on one side, insured nodes on the other, edges weighted by
the claims they share. A repeated pair is the core collusion signal — the same
provider servicing the same insured across many claims.

Issued as grouped queries so the graph is one round-trip per entity table, not
one per node.
"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ramos import normalize_ramo
from app.infrastructure.db.models.asegurado import Asegurado
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.network import NetworkEdge, NetworkNode, NetworkRelations

_RESTRICTIVE_THRESHOLD = 0.5

# Cap on edges so the graph stays readable. Edges are pre-sorted by alert
# weight, so the cap keeps the most suspicious links.
_DEFAULT_EDGE_LIMIT = 60


def _edge_weight(casos: int, alertas: int) -> tuple[int, int]:
    return (alertas, casos)


async def network_relations(
    session: AsyncSession, *, limit: int = _DEFAULT_EDGE_LIMIT
) -> NetworkRelations:
    alerta_case = case((ClaimScore.tier.in_(["amarillo", "rojo"]), 1), else_=0)

    pair_stmt = (
        select(
            Siniestro.beneficiario.label("prov_id"),
            Siniestro.id_asegurado.label("aseg_id"),
            func.count(Siniestro.id_siniestro).label("casos"),
            func.coalesce(func.sum(alerta_case), 0).label("alertas"),
            func.coalesce(func.sum(Siniestro.monto_reclamado), 0.0).label("monto"),
        )
        .select_from(Siniestro)
        .outerjoin(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
        .where(Siniestro.beneficiario.is_not(None))
        .group_by(Siniestro.beneficiario, Siniestro.id_asegurado)
    )
    pair_rows = (await session.execute(pair_stmt)).all()

    # Keep the suspicious sub-network: any alert, or a repeated pair (≥2 shared
    # claims). Fall back to all pairs when nothing qualifies (fresh dataset with
    # no scores yet) so the graph is never empty.
    flagged = [
        r for r in pair_rows if int(r.alertas or 0) >= 1 or int(r.casos or 0) >= 2
    ]
    candidates = flagged or list(pair_rows)
    candidates.sort(
        key=lambda r: _edge_weight(int(r.casos or 0), int(r.alertas or 0)),
        reverse=True,
    )
    selected = candidates[:limit]

    edges = [
        NetworkEdge(
            proveedor_id=r.prov_id,
            asegurado_id=r.aseg_id,
            casos_compartidos=int(r.casos or 0),
            alertas=int(r.alertas or 0),
            monto=float(r.monto or 0.0),
        )
        for r in selected
    ]

    prov_ids = {e.proveedor_id for e in edges}
    aseg_ids = {e.asegurado_id for e in edges}

    nodes: list[NetworkNode] = []
    if prov_ids:
        nodes.extend(await _provider_nodes(session, prov_ids))
    if aseg_ids:
        nodes.extend(await _insured_nodes(session, aseg_ids, edges))

    return NetworkRelations(nodes=nodes, edges=edges)


async def _provider_nodes(
    session: AsyncSession, prov_ids: set[str]
) -> list[NetworkNode]:
    alerta_case = case((ClaimScore.tier.in_(["amarillo", "rojo"]), 1), else_=0)
    agg_stmt = (
        select(
            Siniestro.beneficiario.label("prov_id"),
            func.count(Siniestro.id_siniestro).label("casos"),
            func.coalesce(func.sum(alerta_case), 0).label("alertas"),
            func.coalesce(func.sum(Siniestro.monto_reclamado), 0.0).label("monto"),
            func.array_agg(func.distinct(Siniestro.ramo)).label("ramos"),
        )
        .select_from(Siniestro)
        .outerjoin(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
        .where(Siniestro.beneficiario.in_(prov_ids))
        .group_by(Siniestro.beneficiario)
    )
    agg = {
        r.prov_id: (
            int(r.casos or 0),
            int(r.alertas or 0),
            float(r.monto or 0.0),
            sorted({normalize_ramo(x) for x in (r.ramos or []) if x}),
        )
        for r in (await session.execute(agg_stmt)).all()
    }
    proveedores = (
        (await session.execute(select(Proveedor).where(Proveedor.id_proveedor.in_(prov_ids))))
        .scalars()
        .all()
    )
    nodes: list[NetworkNode] = []
    for p in proveedores:
        casos, alertas, monto, ramos = agg.get(p.id_proveedor, (0, 0, 0.0, []))
        nodes.append(
            NetworkNode(
                id=p.id_proveedor,
                label=p.nombre or f"{p.tipo} {p.id_proveedor}",
                kind="proveedor",
                ciudad=p.ciudad,
                casos=casos,
                alertas=alertas,
                monto=monto,
                lista_restrictiva=p.porcentaje_casos_observados >= _RESTRICTIVE_THRESHOLD,
                ramos=ramos,
            )
        )
    return nodes


async def _insured_nodes(
    session: AsyncSession, aseg_ids: set[str], edges: list[NetworkEdge]
) -> list[NetworkNode]:
    # Roll the edge stats up per insured — avoids a second claims scan.
    casos: dict[str, int] = {}
    alertas: dict[str, int] = {}
    monto: dict[str, float] = {}
    for e in edges:
        casos[e.asegurado_id] = casos.get(e.asegurado_id, 0) + e.casos_compartidos
        alertas[e.asegurado_id] = alertas.get(e.asegurado_id, 0) + e.alertas
        monto[e.asegurado_id] = monto.get(e.asegurado_id, 0.0) + e.monto

    asegurados = (
        (await session.execute(select(Asegurado).where(Asegurado.id_asegurado.in_(aseg_ids))))
        .scalars()
        .all()
    )
    return [
        NetworkNode(
            id=a.id_asegurado,
            label=a.nombre or a.id_asegurado,
            kind="asegurado",
            ciudad=a.ciudad,
            casos=casos.get(a.id_asegurado, 0),
            alertas=alertas.get(a.id_asegurado, 0),
            monto=monto.get(a.id_asegurado, 0.0),
        )
        for a in asegurados
    ]
