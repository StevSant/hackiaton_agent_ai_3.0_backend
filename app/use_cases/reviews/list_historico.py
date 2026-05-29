"""list_historico — paginated histórico for analista and antifraude."""

from __future__ import annotations

from datetime import UTC, datetime

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.domain.ramos import normalize_ramo
from app.infrastructure.reviews.ports import ReviewsStore
from app.schemas.claim import ClaimDetail, ClaimReview, ClaimSummary
from app.schemas.page import Page

_OLDEST_EVENT_AT = datetime.min.replace(tzinfo=UTC)


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
    pairs.sort(key=lambda pair: pair[1].dictaminado_at or _OLDEST_EVENT_AT, reverse=True)
    summaries: list[ClaimSummary] = []
    for claim_id, review in pairs:
        detail = await queries.get_detail(claim_id)
        if detail is None:
            continue
        summaries.append(_summary_from_review(detail, review))

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
    pairs.sort(key=lambda pair: _history_event_at(pair[1]), reverse=True)
    summaries: list[ClaimSummary] = []
    for claim_id, review in pairs:
        detail = await queries.get_detail(claim_id)
        if detail is None:
            continue
        summaries.append(_summary_from_review(detail, review))

    total = len(summaries)
    start = page * page_size
    return Page(
        items=summaries[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


def _history_event_at(review: ClaimReview) -> datetime:
    return review.dictaminado_at or review.closed_at or review.escalated_at or _OLDEST_EVENT_AT


def _summary_from_review(detail: ClaimDetail, review: ClaimReview) -> ClaimSummary:
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
        review_status=review.status,
        dictamen_outcome=review.dictamen_outcome,
        dictamen_justificacion=review.dictamen_justificacion,
        dictaminado_at=review.dictaminado_at,
    )
