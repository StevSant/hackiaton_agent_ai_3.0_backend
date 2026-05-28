"""list_historico — paginated histórico for analista and antifraude."""

from __future__ import annotations

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.domain.ramos import normalize_ramo
from app.infrastructure.reviews.ports import ReviewsStore
from app.schemas.claim import ClaimSummary
from app.schemas.page import Page


async def list_antifraude_historico(
    store: ReviewsStore,
    queries: ClaimQueries,
    *,
    user_id: str,
    page: int = 0,
    page_size: int = 25,
) -> Page[ClaimSummary]:
    """Paginated dictámenes emitted by *user_id* (antifraude historico)."""
    pairs = await store.list_dictaminado_by(user_id)
    summaries: list[ClaimSummary] = []
    for claim_id, review in pairs:
        detail = await queries.get_detail(claim_id)
        if detail is None:
            continue
        summaries.append(
            ClaimSummary(
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
                review_status=review.status,
            )
        )

    total = len(summaries)
    start = page * page_size
    return Page(
        items=summaries[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


async def list_analista_historico(
    store: ReviewsStore,
    queries: ClaimQueries,
    *,
    user_id: str,
    page: int = 0,
    page_size: int = 25,
) -> Page[ClaimSummary]:
    """Paginated closed cases for the analista.

    Includes revisado_sin_escalar (her own) + dictaminado (cases she escalated).
    """
    pairs = await store.list_closed_by(user_id)
    summaries: list[ClaimSummary] = []
    for claim_id, review in pairs:
        detail = await queries.get_detail(claim_id)
        if detail is None:
            continue
        summaries.append(
            ClaimSummary(
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
                review_status=review.status,
            )
        )

    total = len(summaries)
    start = page * page_size
    return Page(
        items=summaries[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )
