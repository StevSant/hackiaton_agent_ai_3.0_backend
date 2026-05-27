"""In-memory `ClaimQueries` impl — used by tests and as the dev fallback before
Miquel's lane lands the SQLAlchemy-backed `DbClaimQueries`.

Operates over an in-process list of `ClaimDetail` fixtures + the alert chips on
each, so the agent's 12 NL questions are answerable end-to-end without a database.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import cast

from app.agents.claims_agent.tools.types import (
    AggregateDimension,
    AggregateRow,
    ExecutiveSummary,
    MissingDocClaim,
    TierFilter,
)
from app.schemas.claim import ClaimDetail, ClaimSummary
from app.schemas.risk import Tier

_TIER_FILTERS: dict[TierFilter, set[Tier]] = {
    "rojo": {Tier.rojo},
    "amarillo": {Tier.amarillo},
    "amarillo+rojo": {Tier.amarillo, Tier.rojo},
    "all": {Tier.verde, Tier.amarillo, Tier.rojo},
}


class InMemoryClaimQueries:
    """`ClaimQueries` impl over an in-process list of `ClaimDetail` fixtures."""

    def __init__(self, claims: list[ClaimDetail]) -> None:
        self._claims: list[ClaimDetail] = list(claims)

    # --- helpers -------------------------------------------------------------

    def _filter_by_tier(self, claims: list[ClaimDetail], tier: TierFilter) -> list[ClaimDetail]:
        allowed = _TIER_FILTERS[tier]
        return [c for c in claims if c.nivel in allowed]

    def _to_summary(self, c: ClaimDetail) -> ClaimSummary:
        return ClaimSummary(
            id=c.id,
            ramo=c.ramo,
            cobertura=c.cobertura,
            asegurado=c.asegurado,
            ciudad=c.ciudad,
            fecha_ocurrencia=c.fecha_ocurrencia,
            monto_reclamado=c.monto_reclamado,
            estado=c.estado,
            score=c.score,
            nivel=c.nivel,
            review_status=c.review.status,
        )

    # --- ClaimQueries interface ---------------------------------------------

    async def list_top_risk(
        self, *, top_n: int = 10, tier: TierFilter = "amarillo+rojo"
    ) -> list[ClaimSummary]:
        filtered = self._filter_by_tier(self._claims, tier)
        ranked = sorted(filtered, key=lambda c: c.score, reverse=True)[:top_n]
        return [self._to_summary(c) for c in ranked]

    async def get_detail(self, claim_id: str) -> ClaimDetail | None:
        return next((c for c in self._claims if c.id == claim_id), None)

    async def aggregate(
        self,
        *,
        dimension: AggregateDimension,
        tier: TierFilter = "amarillo+rojo",
        top_n: int = 10,
    ) -> list[AggregateRow]:
        filtered = self._filter_by_tier(self._claims, tier)
        if not filtered:
            return []
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
            key_s = str(key)
            counts[key_s] += 1
            example.setdefault(key_s, c.id)
        total = sum(counts.values()) or 1
        rows = [
            AggregateRow(
                key=key,
                count=count,
                pct=round(100.0 * count / total, 1),
                example_claim_id=example.get(key),
            )
            for key, count in counts.most_common(top_n)
        ]
        return rows

    async def missing_documents(
        self, *, top_n: int = 10, tier: TierFilter = "amarillo+rojo"
    ) -> list[MissingDocClaim]:
        filtered = self._filter_by_tier(self._claims, tier)
        rows: list[MissingDocClaim] = []
        for c in filtered:
            missing = [d.tipo for d in c.documentos if d.falta or d.estado.lower() == "pendiente"]
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
        self, *, window_days: int = 10, top_n: int = 10
    ) -> list[ClaimSummary]:
        # Without the polizas table, we approximate: pick claims with FS-01 in their
        # alert chips OR a low `dias_desde_inicio_poliza` derived field (not present
        # on ClaimDetail — so we just filter by FS-01 alert). Once Miquel's lane lands
        # the polizas join, replace this with a proper days-since-policy-start query.
        matching = [
            c for c in self._claims if any(a.code == "FS-01" for a in c.alertas)
        ]
        ranked = sorted(matching, key=lambda c: c.score, reverse=True)[:top_n]
        return [self._to_summary(c) for c in ranked]

    async def recommend_review(self, *, top_n: int = 5) -> list[ClaimSummary]:
        # Recommend: rojo first, then amarillo with most alert points
        rojo = [c for c in self._claims if c.nivel == Tier.rojo]
        amarillo = sorted(
            (c for c in self._claims if c.nivel == Tier.amarillo),
            key=lambda c: c.score,
            reverse=True,
        )
        ordered = sorted(rojo, key=lambda c: c.score, reverse=True) + amarillo
        return [self._to_summary(c) for c in ordered[:top_n]]

    async def executive_summary(self) -> ExecutiveSummary:
        by_tier: Counter[Tier] = Counter(c.nivel for c in self._claims)
        top_rojo = [
            self._to_summary(c)
            for c in sorted(
                (c for c in self._claims if c.nivel == Tier.rojo),
                key=lambda c: c.score,
                reverse=True,
            )[:5]
        ]
        critical = [c for c in self._claims if c.nivel in {Tier.amarillo, Tier.rojo}]
        prov_counter: Counter[str] = Counter(
            cast(str, c.proveedor) for c in critical if c.proveedor
        )
        ramo_counter: Counter[str] = Counter(c.ramo for c in critical if c.ramo)
        return ExecutiveSummary(
            total_claims=len(self._claims),
            rojo_count=by_tier.get(Tier.rojo, 0),
            amarillo_count=by_tier.get(Tier.amarillo, 0),
            verde_count=by_tier.get(Tier.verde, 0),
            top_rojo=top_rojo,
            top_proveedores=[p for p, _ in prov_counter.most_common(5)],
            top_ramos=[r for r, _ in ramo_counter.most_common(5)],
        )
