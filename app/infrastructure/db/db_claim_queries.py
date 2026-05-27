"""DbClaimQueries — `ClaimQueries` port backed by AsyncSession.

Implements the same interface as InMemoryClaimQueries so the agent tools
and API routes need no changes when CLAIMS_SOURCE=db is set.

Reads the persisted claim_scores rows (score / tier / activations) — does NOT
re-score on read.  The score is the one written by load_dataset at ingest time.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.claims_agent.tools.types import (
    AggregateDimension,
    AggregateRow,
    ExecutiveSummary,
    MissingDocClaim,
    TierFilter,
)
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.documento import Documento
from app.infrastructure.db.models.poliza import Poliza
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.claim import ClaimDetail, ClaimSummary
from app.schemas.risk import Tier
from app.use_cases.load_dataset._mapping import rows_to_claim_detail

_TIER_FILTERS: dict[TierFilter, set[Tier]] = {
    "rojo": {Tier.rojo},
    "amarillo": {Tier.amarillo},
    "amarillo+rojo": {Tier.amarillo, Tier.rojo},
    "all": {Tier.verde, Tier.amarillo, Tier.rojo},
}


class DbClaimQueries:
    """`ClaimQueries` port implementation over `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _load_detail(self, sin: Siniestro) -> ClaimDetail:
        """Hydrate a ClaimDetail from a Siniestro ORM object + related rows."""
        pol: Poliza | None = await self._s.get(Poliza, sin.id_poliza)

        score_stmt = select(ClaimScore).where(ClaimScore.claim_id == sin.id_siniestro)
        score_row: ClaimScore | None = (
            await self._s.execute(score_stmt)
        ).scalars().first()

        doc_stmt = select(Documento).where(Documento.id_siniestro == sin.id_siniestro)
        documentos: list[Documento] = list(
            (await self._s.execute(doc_stmt)).scalars().all()
        )

        return rows_to_claim_detail(sin, pol, score_row, documentos)

    def _to_summary(self, detail: ClaimDetail) -> ClaimSummary:
        return ClaimSummary(
            id=detail.id,
            ramo=detail.ramo,
            cobertura=detail.cobertura,
            asegurado=detail.asegurado,
            ciudad=detail.ciudad,
            fecha_ocurrencia=detail.fecha_ocurrencia,
            monto_reclamado=detail.monto_reclamado,
            estado=detail.estado,
            score=detail.score,
            nivel=detail.nivel,
            review_status=detail.review.status,
        )

    async def _all_details(self) -> list[ClaimDetail]:
        """Load every claim with its score in one pass."""
        stmt = select(Siniestro)
        sins: list[Siniestro] = list(
            (await self._s.execute(stmt)).scalars().all()
        )
        results: list[ClaimDetail] = []
        for sin in sins:
            results.append(await self._load_detail(sin))
        return results

    def _filter_by_tier(
        self, claims: list[ClaimDetail], tier: TierFilter
    ) -> list[ClaimDetail]:
        allowed = _TIER_FILTERS[tier]
        return [c for c in claims if c.nivel in allowed]

    # ------------------------------------------------------------------
    # ClaimQueries port
    # ------------------------------------------------------------------

    async def get_detail(self, claim_id: str) -> ClaimDetail | None:
        sin: Siniestro | None = await self._s.get(Siniestro, claim_id)
        if sin is None:
            return None
        return await self._load_detail(sin)

    async def list_top_risk(
        self,
        *,
        top_n: int = 10,
        tier: TierFilter = "amarillo+rojo",
    ) -> list[ClaimSummary]:
        allowed_tiers = [t.value for t in _TIER_FILTERS[tier]]
        # Join siniestros ↔ claim_scores, filter by tier, order by score DESC
        stmt = (
            select(Siniestro, ClaimScore)
            .join(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .where(ClaimScore.tier.in_(allowed_tiers))
            .order_by(ClaimScore.score.desc())
            .limit(top_n)
        )
        rows = list((await self._s.execute(stmt)).all())
        results: list[ClaimSummary] = []
        for sin, score_row in rows:
            pol: Poliza | None = await self._s.get(Poliza, sin.id_poliza)
            doc_stmt = select(Documento).where(
                Documento.id_siniestro == sin.id_siniestro
            )
            docs = list((await self._s.execute(doc_stmt)).scalars().all())
            detail = rows_to_claim_detail(sin, pol, score_row, docs)
            results.append(self._to_summary(detail))
        return results

    async def aggregate(
        self,
        *,
        dimension: AggregateDimension,
        tier: TierFilter = "amarillo+rojo",
        top_n: int = 10,
    ) -> list[AggregateRow]:
        claims = await self._all_details()
        filtered = self._filter_by_tier(claims, tier)
        if not filtered:
            return []
        from collections.abc import Callable

        key_for: dict[AggregateDimension, Callable[[ClaimDetail], str | None]] = {
            "proveedor": lambda c: c.proveedor,
            "ramo": lambda c: c.ramo,
            "ciudad": lambda c: c.ciudad,
            "asegurado": lambda c: c.asegurado,
        }
        getter = key_for[dimension]
        counts: Counter[str] = Counter()
        example: dict[str, str] = {}
        for c in filtered:
            key = getter(c)
            if not key:
                continue
            counts[key] += 1
            example.setdefault(key, c.id)
        total = sum(counts.values()) or 1
        return [
            AggregateRow(
                key=k,
                count=cnt,
                pct=round(100.0 * cnt / total, 1),
                example_claim_id=example.get(k),
            )
            for k, cnt in counts.most_common(top_n)
        ]

    async def missing_documents(
        self,
        *,
        top_n: int = 10,
        tier: TierFilter = "amarillo+rojo",
    ) -> list[MissingDocClaim]:
        claims = await self._all_details()
        filtered = self._filter_by_tier(claims, tier)
        rows: list[MissingDocClaim] = []
        for c in filtered:
            missing = [
                d.tipo for d in c.documentos if d.falta or d.estado.lower() == "pendiente"
            ]
            if missing:
                rows.append(
                    MissingDocClaim(
                        claim_id=c.id,
                        nivel=c.nivel.value,
                        score=c.score,
                        documentos_faltantes=missing,
                    )
                )
        rows.sort(key=lambda r: r.score, reverse=True)
        return rows[:top_n]

    async def claims_near_policy_start(
        self,
        *,
        window_days: int = 10,
        top_n: int = 10,
    ) -> list[ClaimSummary]:
        # Use the pre-computed dias_desde_inicio_poliza column for efficiency
        stmt = (
            select(Siniestro, ClaimScore)
            .join(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .where(Siniestro.dias_desde_inicio_poliza <= window_days)
            .order_by(ClaimScore.score.desc())
            .limit(top_n)
        )
        rows = list((await self._s.execute(stmt)).all())
        results: list[ClaimSummary] = []
        for sin, score_row in rows:
            pol: Poliza | None = await self._s.get(Poliza, sin.id_poliza)
            doc_stmt = select(Documento).where(
                Documento.id_siniestro == sin.id_siniestro
            )
            docs = list((await self._s.execute(doc_stmt)).scalars().all())
            detail = rows_to_claim_detail(sin, pol, score_row, docs)
            results.append(self._to_summary(detail))
        return results

    async def recommend_review(self, *, top_n: int = 5) -> list[ClaimSummary]:
        # Rojo first (score desc), then amarillo (score desc)
        rojo_stmt = (
            select(Siniestro, ClaimScore)
            .join(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .where(ClaimScore.tier == Tier.rojo.value)
            .order_by(ClaimScore.score.desc())
        )
        amarillo_stmt = (
            select(Siniestro, ClaimScore)
            .join(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .where(ClaimScore.tier == Tier.amarillo.value)
            .order_by(ClaimScore.score.desc())
        )
        rojo_rows = list((await self._s.execute(rojo_stmt)).all())
        amarillo_rows = list((await self._s.execute(amarillo_stmt)).all())
        ordered = (rojo_rows + amarillo_rows)[:top_n]
        results: list[ClaimSummary] = []
        for sin, score_row in ordered:
            pol: Poliza | None = await self._s.get(Poliza, sin.id_poliza)
            doc_stmt = select(Documento).where(
                Documento.id_siniestro == sin.id_siniestro
            )
            docs = list((await self._s.execute(doc_stmt)).scalars().all())
            detail = rows_to_claim_detail(sin, pol, score_row, docs)
            results.append(self._to_summary(detail))
        return results

    async def executive_summary(self) -> ExecutiveSummary:
        claims = await self._all_details()
        by_tier: Counter[Tier] = Counter(c.nivel for c in claims)
        top_rojo = [
            self._to_summary(c)
            for c in sorted(
                (c for c in claims if c.nivel == Tier.rojo),
                key=lambda c: c.score,
                reverse=True,
            )[:5]
        ]
        critical = [c for c in claims if c.nivel in {Tier.amarillo, Tier.rojo}]
        prov_counter: Counter[str] = Counter(
            c.proveedor for c in critical if c.proveedor
        )
        ramo_counter: Counter[str] = Counter(c.ramo for c in critical if c.ramo)
        return ExecutiveSummary(
            total_claims=len(claims),
            rojo_count=by_tier.get(Tier.rojo, 0),
            amarillo_count=by_tier.get(Tier.amarillo, 0),
            verde_count=by_tier.get(Tier.verde, 0),
            top_rojo=top_rojo,
            top_proveedores=[p for p, _ in prov_counter.most_common(5)],
            top_ramos=[r for r, _ in ramo_counter.most_common(5)],
        )
