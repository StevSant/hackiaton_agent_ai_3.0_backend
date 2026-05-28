"""DbClaimQueries — `ClaimQueries` port backed by AsyncSession.

Sole runtime implementation of `ClaimQueries`. Reads the persisted
`claim_scores` rows (score / tier / activations) — does NOT re-score on read.
The score is the one written by load_dataset at ingest time.

`InMemoryClaimQueries` is kept only for tests; production never wires it.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, TypeVar
from uuid import UUID

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

if TYPE_CHECKING:
    from app.agents.claims_agent.tools.get_asegurado_detail_tool import (
        GetAseguradoDetailOutput,
    )
    from app.agents.claims_agent.tools.get_provider_detail_tool import (
        GetProviderDetailOutput,
    )

_T = TypeVar("_T", bound=tuple[object, ...])

from app.agents.claims_agent.tools.types import (
    AggregateDimension,
    AggregateRow,
    ExecutiveSummary,
    MissingDocClaim,
    TierFilter,
)
from app.domain.ramos import normalize_ramo
from app.infrastructure.db.models.asegurado import Asegurado
from app.infrastructure.db.models.claim_review import ClaimReview as ClaimReviewRow
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.documento import Documento
from app.infrastructure.db.models.poliza import Poliza
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.claim import ClaimDetail, ClaimSummary, ReviewStatus
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

    def __init__(
        self,
        session: AsyncSession,
        *,
        workspace_id: UUID | None = None,
    ) -> None:
        self._s = session
        self._workspace_id = workspace_id

    def _can_access(self, sin: Siniestro) -> bool:
        if self._workspace_id is None:
            return True
        return sin.workspace_id is None or sin.workspace_id == self._workspace_id

    def _apply_workspace(self, stmt: Select[_T]) -> Select[_T]:
        if self._workspace_id is None:
            return stmt
        return stmt.where(
            or_(
                Siniestro.workspace_id.is_(None),
                Siniestro.workspace_id == self._workspace_id,
            )
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _load_detail(self, sin: Siniestro) -> ClaimDetail:
        """Hydrate a ClaimDetail from a Siniestro ORM object + related rows.

        Single round-trip per claim: re-select with `selectinload` populating
        poliza / asegurado / documentos / score in one batch, then fetch the
        provider (no ORM relationship to selectinload because beneficiario is
        a free-form FK string).
        """
        # populate_existing=True is REQUIRED: `get_detail` already fetched `sin`
        # via session.get(), seeding the identity map with the instance whose
        # relationships are `lazy="noload"` (i.e. resolved to None). Without
        # populate_existing, this re-select returns that same cached instance and
        # selectinload silently skips it, leaving poliza/score = None — which made
        # get_claim_detail fall back to the context-poor live-rescore path and
        # clobber the baked score (showed 0 / wrong score, suma=0, ciudad="").
        stmt = (
            select(Siniestro)
            .options(
                selectinload(Siniestro.poliza),
                selectinload(Siniestro.asegurado),
                selectinload(Siniestro.documentos),
                selectinload(Siniestro.score),
            )
            .where(Siniestro.id_siniestro == sin.id_siniestro)
            .execution_options(populate_existing=True)
        )
        loaded = (await self._s.execute(stmt)).scalars().first() or sin
        proveedor: Proveedor | None = (
            await self._s.get(Proveedor, loaded.beneficiario) if loaded.beneficiario else None
        )
        return rows_to_claim_detail(
            loaded,
            loaded.poliza,
            loaded.score,
            list(loaded.documentos),
            proveedor,
            asegurado=loaded.asegurado,
        )

    async def _hydrate(self, sin: Siniestro, score_row: ClaimScore) -> ClaimDetail:
        """Hydrate a ClaimDetail from a (sin, score) pair already in hand."""
        pol: Poliza | None = await self._s.get(Poliza, sin.id_poliza)
        doc_stmt = select(Documento).where(Documento.id_siniestro == sin.id_siniestro)
        docs = list((await self._s.execute(doc_stmt)).scalars().all())
        proveedor: Proveedor | None = (
            await self._s.get(Proveedor, sin.beneficiario) if sin.beneficiario else None
        )
        asegurado: Asegurado | None = await self._s.get(Asegurado, sin.id_asegurado)
        return rows_to_claim_detail(
            sin, pol, score_row, docs, proveedor, asegurado=asegurado
        )

    def _build_summary(
        self,
        sin: Siniestro,
        score_row: ClaimScore,
        ciudad: str | None,
        asegurado_nombre: str | None = None,
        review_status: str | None = None,
        proveedor_nombre: str | None = None,
    ) -> ClaimSummary:
        """Build a ClaimSummary directly from ORM rows — no docs/proveedor fetch.

        Summary listings don't fetch a full Proveedor row, so the join in
        :meth:`list_top_risk` passes the provider's display name (and id, via
        ``sin.beneficiario``) directly here. The provider detail page uses these
        to count the rows it owns.
        """
        display = (
            asegurado_nombre
            if asegurado_nombre
            else f"Asegurado {sin.id_asegurado[-4:]}"
        )
        proveedor_display = (
            proveedor_nombre or sin.beneficiario if sin.beneficiario else None
        )
        return ClaimSummary(
            id=sin.id_siniestro,
            ramo=normalize_ramo(sin.ramo),
            cobertura=sin.cobertura,
            asegurado=display,
            asegurado_id=sin.id_asegurado,
            ciudad=ciudad or "",
            fecha_ocurrencia=sin.fecha_ocurrencia,
            monto_reclamado=sin.monto_reclamado,
            estado=sin.estado,
            score=score_row.score,
            nivel=Tier(score_row.tier),
            review_status=(
                ReviewStatus(review_status) if review_status else ReviewStatus.pendiente
            ),
            proveedor=proveedor_display,
            proveedor_id=sin.beneficiario,
        )

    def _to_summary(self, detail: ClaimDetail) -> ClaimSummary:
        """ClaimDetail → ClaimSummary. Used by executive_summary (already-hydrated path)."""
        return ClaimSummary(
            id=detail.id,
            ramo=normalize_ramo(detail.ramo),
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
        """Load every claim with its score / relations in one pass.

        Eager-loads poliza, asegurado, documentos, and score with
        ``selectinload`` (≈5 queries total instead of N×5). Providers don't
        have an ORM relationship on Siniestro (beneficiario is a loose FK
        string), so we bulk-fetch them by id in one extra query.

        Memoized on the SQLAlchemy session: when the agent's tool dispatcher
        runs ``aggregate`` + ``missing_documents`` + ``executive_summary`` on
        the same session, the second and third callers reuse the first call's
        result instead of refetching.
        """
        cache_key = f"_all_details:{self._workspace_id}"
        cached = self._s.info.get(cache_key)
        if cached is not None:
            return cached

        stmt = (
            select(Siniestro)
            .options(
                selectinload(Siniestro.poliza),
                selectinload(Siniestro.asegurado),
                selectinload(Siniestro.documentos),
                selectinload(Siniestro.score),
            )
        )
        stmt = self._apply_workspace(stmt)
        sins: list[Siniestro] = list((await self._s.execute(stmt)).scalars().all())

        # Bulk-fetch providers by id (no relationship to selectinload).
        provedor_ids = {s.beneficiario for s in sins if s.beneficiario}
        provs: dict[str, Proveedor] = {}
        if provedor_ids:
            prov_stmt = select(Proveedor).where(Proveedor.id_proveedor.in_(provedor_ids))
            for prov in (await self._s.execute(prov_stmt)).scalars().all():
                provs[prov.id_proveedor] = prov

        results = [
            rows_to_claim_detail(
                sin,
                sin.poliza,
                sin.score,
                list(sin.documentos),
                provs.get(sin.beneficiario) if sin.beneficiario else None,
                asegurado=sin.asegurado,
            )
            for sin in sins
        ]
        self._s.info[cache_key] = results
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
        if sin is None or not self._can_access(sin):
            return None
        return await self._load_detail(sin)

    async def list_top_risk(
        self,
        *,
        top_n: int = 10,
        tier: TierFilter = "amarillo+rojo",
    ) -> list[ClaimSummary]:
        allowed_tiers = [t.value for t in _TIER_FILTERS[tier]]
        # Single joined query: siniestros ⨝ claim_scores ⨝ polizas ⨝ asegurados
        # ⨝ claim_reviews ⨝ proveedores. All non-score joins are LEFT — claims
        # without a review row are pendiente by default; claims with no
        # proveedor return null for proveedor_nombre.
        stmt = (
            select(
                Siniestro,
                ClaimScore,
                Poliza.ciudad,
                Asegurado.nombre,
                ClaimReviewRow.status,
                Proveedor.nombre.label("proveedor_nombre"),
            )
            .join(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .outerjoin(Poliza, Poliza.id_poliza == Siniestro.id_poliza)
            .outerjoin(Asegurado, Asegurado.id_asegurado == Siniestro.id_asegurado)
            .outerjoin(
                ClaimReviewRow, ClaimReviewRow.claim_id == Siniestro.id_siniestro
            )
            .outerjoin(Proveedor, Proveedor.id_proveedor == Siniestro.beneficiario)
            .where(ClaimScore.tier.in_(allowed_tiers))
            .order_by(ClaimScore.score.desc())
            .limit(top_n)
        )
        stmt = self._apply_workspace(stmt)
        rows = list((await self._s.execute(stmt)).all())
        return [
            self._build_summary(
                sin,
                score_row,
                ciudad,
                asegurado_nombre=nombre,
                review_status=review_status,
                proveedor_nombre=proveedor_nombre,
            )
            for sin, score_row, ciudad, nombre, review_status, proveedor_nombre in rows
        ]

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
        # Use the pre-computed dias_desde_inicio_poliza column for efficiency.
        # Single joined query (incl. Poliza.ciudad + Asegurado.nombre) — no per-row N+1.
        stmt = (
            select(Siniestro, ClaimScore, Poliza.ciudad, Asegurado.nombre)
            .join(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .outerjoin(Poliza, Poliza.id_poliza == Siniestro.id_poliza)
            .outerjoin(Asegurado, Asegurado.id_asegurado == Siniestro.id_asegurado)
            .where(Siniestro.dias_desde_inicio_poliza <= window_days)
            .order_by(ClaimScore.score.desc())
            .limit(top_n)
        )
        stmt = self._apply_workspace(stmt)
        rows = list((await self._s.execute(stmt)).all())
        return [
            self._build_summary(sin, score_row, ciudad, asegurado_nombre=nombre)
            for sin, score_row, ciudad, nombre in rows
        ]

    async def recommend_review(self, *, top_n: int = 5) -> list[ClaimSummary]:
        # Rojo first (score desc), then amarillo (score desc).
        # Single joined query per tier (incl. Poliza.ciudad + Asegurado.nombre) — no per-row N+1.
        base = (
            select(Siniestro, ClaimScore, Poliza.ciudad, Asegurado.nombre)
            .join(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .outerjoin(Poliza, Poliza.id_poliza == Siniestro.id_poliza)
            .outerjoin(Asegurado, Asegurado.id_asegurado == Siniestro.id_asegurado)
        )
        rojo_stmt = self._apply_workspace(
            base.where(ClaimScore.tier == Tier.rojo.value).order_by(ClaimScore.score.desc())
        )
        amarillo_stmt = self._apply_workspace(
            base.where(ClaimScore.tier == Tier.amarillo.value).order_by(ClaimScore.score.desc())
        )
        rojo_rows = list((await self._s.execute(rojo_stmt)).all())
        amarillo_rows = list((await self._s.execute(amarillo_stmt)).all())
        ordered = (rojo_rows + amarillo_rows)[:top_n]
        return [
            self._build_summary(sin, score_row, ciudad, asegurado_nombre=nombre)
            for sin, score_row, ciudad, nombre in ordered
        ]

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

    async def get_provider_detail(
        self, provider_id: str, *, top_claims: int = 5
    ) -> "GetProviderDetailOutput | None":
        """Ficha completa de un proveedor + sus top-N siniestros por score."""
        from app.agents.claims_agent.tools.get_provider_detail_tool import (
            GetProviderDetailOutput,
        )
        from app.domain.ramos import normalize_ramo
        from app.schemas.network import ProviderOut

        proveedor: Proveedor | None = await self._s.get(Proveedor, provider_id)
        if proveedor is None:
            return None

        # Aggregate ramos for this provider
        alerta_case = case(
            (ClaimScore.tier.in_(["amarillo", "rojo"]), 1),
            else_=0,
        )
        agg_stmt = (
            select(
                func.count(Siniestro.id_siniestro).label("casos"),
                func.coalesce(func.sum(Siniestro.monto_reclamado), 0.0).label("monto"),
                func.coalesce(func.sum(alerta_case), 0).label("alertas"),
                func.array_agg(func.distinct(Siniestro.ramo)).label("ramos"),
            )
            .select_from(Siniestro)
            .outerjoin(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .where(Siniestro.beneficiario == provider_id)
        )
        agg_row = (await self._s.execute(agg_stmt)).one()
        casos = int(agg_row.casos or 0)
        alertas = int(agg_row.alertas or 0)
        raw_ramos: list[str] = [r for r in (agg_row.ramos or []) if r]
        ramos = sorted({normalize_ramo(r) for r in raw_ramos})

        _RESTRICTIVE_THRESHOLD = 0.5
        nombre = proveedor.nombre or f"{proveedor.tipo} {proveedor.id_proveedor}"
        provider_out = ProviderOut(
            id_proveedor=proveedor.id_proveedor,
            nombre=nombre,
            tipo=proveedor.tipo,
            ciudad=proveedor.ciudad,
            casos=casos,
            alertas=alertas,
            monto=float(agg_row.monto or 0.0),
            lista_restrictiva=proveedor.porcentaje_casos_observados >= _RESTRICTIVE_THRESHOLD,
            ramos=ramos,
        )

        # Top-N claims by score for this provider
        top_stmt = (
            select(Siniestro, ClaimScore, Poliza.ciudad, Asegurado.nombre)
            .join(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .outerjoin(Poliza, Poliza.id_poliza == Siniestro.id_poliza)
            .outerjoin(Asegurado, Asegurado.id_asegurado == Siniestro.id_asegurado)
            .where(Siniestro.beneficiario == provider_id)
            .order_by(ClaimScore.score.desc())
            .limit(top_claims)
        )
        top_stmt = self._apply_workspace(top_stmt)
        top_rows = list((await self._s.execute(top_stmt)).all())
        top_claim_summaries = [
            self._build_summary(sin, score_row, ciudad, asegurado_nombre=nombre)
            for sin, score_row, ciudad, nombre in top_rows
        ]

        return GetProviderDetailOutput(
            found=True,
            provider=provider_out,
            top_claims=top_claim_summaries,
        )

    async def get_asegurado_detail(
        self, asegurado_id: str, *, top_claims: int = 5
    ) -> "GetAseguradoDetailOutput | None":
        """Ficha completa de un asegurado + sus top-N siniestros por score."""
        from app.agents.claims_agent.tools.get_asegurado_detail_tool import (
            GetAseguradoDetailOutput,
        )
        from app.domain.ramos import normalize_ramo
        from app.schemas.asegurados import AseguradoOut

        asegurado: Asegurado | None = await self._s.get(Asegurado, asegurado_id)
        if asegurado is None:
            return None

        alerta_case = case(
            (ClaimScore.tier.in_(["amarillo", "rojo"]), 1),
            else_=0,
        )
        agg_stmt = (
            select(
                func.count(Siniestro.id_siniestro).label("casos"),
                func.coalesce(func.sum(Siniestro.monto_reclamado), 0.0).label("monto"),
                func.coalesce(func.sum(alerta_case), 0).label("alertas"),
                func.array_agg(func.distinct(Siniestro.ramo)).label("ramos"),
            )
            .select_from(Siniestro)
            .outerjoin(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .where(Siniestro.id_asegurado == asegurado_id)
        )
        agg_row = (await self._s.execute(agg_stmt)).one()
        casos = int(agg_row.casos or 0)
        alertas = int(agg_row.alertas or 0)
        raw_ramos: list[str] = [r for r in (agg_row.ramos or []) if r]
        ramos = sorted({normalize_ramo(r) for r in raw_ramos})

        nombre = asegurado.nombre or f"Asegurado {asegurado.id_asegurado[-4:]}"
        asegurado_out = AseguradoOut(
            id_asegurado=asegurado.id_asegurado,
            nombre=nombre,
            segmento=asegurado.segmento,
            ciudad=asegurado.ciudad,
            antiguedad=asegurado.antiguedad,
            num_polizas=asegurado.num_polizas,
            reclamos_ultimos_12_meses=asegurado.reclamos_ultimos_12_meses,
            mora_actual=asegurado.mora_actual,
            score_cliente_simulado=asegurado.score_cliente_simulado,
            casos=casos,
            alertas=alertas,
            monto=float(agg_row.monto or 0.0),
            ramos=ramos,
        )

        # Top-N claims by score for this asegurado
        top_stmt = (
            select(Siniestro, ClaimScore, Poliza.ciudad, Asegurado.nombre)
            .join(ClaimScore, ClaimScore.claim_id == Siniestro.id_siniestro)
            .outerjoin(Poliza, Poliza.id_poliza == Siniestro.id_poliza)
            .outerjoin(Asegurado, Asegurado.id_asegurado == Siniestro.id_asegurado)
            .where(Siniestro.id_asegurado == asegurado_id)
            .order_by(ClaimScore.score.desc())
            .limit(top_claims)
        )
        top_stmt = self._apply_workspace(top_stmt)
        top_rows = list((await self._s.execute(top_stmt)).all())
        top_claim_summaries = [
            self._build_summary(sin, score_row, ciudad, asegurado_nombre=ase_nombre)
            for sin, score_row, ciudad, ase_nombre in top_rows
        ]

        return GetAseguradoDetailOutput(
            found=True,
            asegurado=asegurado_out,
            top_claims=top_claim_summaries,
        )
