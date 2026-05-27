"""list_antifraude_inbox — paginated inbox for antifraude (GET /antifraude/inbox)."""

from __future__ import annotations

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.domain.ramos import normalize_ramo
from app.infrastructure.reviews.in_memory_reviews_store import InMemoryReviewsStore
from app.schemas.claim import ReviewStatus
from app.schemas.page import Page
from app.schemas.reviews import InboxRow
from app.schemas.risk import Tier

_TIER_ORDER = {"rojo": 0, "amarillo": 1, "verde": 2}


async def list_antifraude_inbox(
    store: InMemoryReviewsStore,
    queries: ClaimQueries,
    *,
    status_filter: ReviewStatus | None = None,
    page: int = 0,
    page_size: int = 25,
) -> Page[InboxRow]:
    """Return the antifraude inbox, sorted by tier desc then escalated_at asc.

    Default filter: escalado + en_revision (active queue).
    """
    if status_filter is not None:
        pairs = store.list_by_status(status_filter)
    else:
        pairs = store.list_by_status(ReviewStatus.escalado, ReviewStatus.en_revision)

    rows: list[InboxRow] = []
    for claim_id, review in pairs:
        detail = await queries.get_detail(claim_id)
        if detail is None:
            # Seed rows have fictional IDs — synthesize a minimal InboxRow
            rows.append(
                InboxRow(
                    claim_id=claim_id,
                    asegurado="(demo seed)",
                    ramo="vehiculos",
                    score=85,
                    nivel=Tier.rojo,
                    escalated_at=review.escalated_at,
                    escalation_note_preview=(review.escalation_note or "")[:120] or None,
                    assigned_to_name=review.assigned_to_name,
                    bounce_count=review.bounce_count,
                )
            )
            continue

        rows.append(
            InboxRow(
                claim_id=claim_id,
                asegurado=detail.asegurado,
                ramo=normalize_ramo(detail.ramo),
                score=detail.score,
                nivel=detail.nivel,
                escalated_at=review.escalated_at,
                escalation_note_preview=(review.escalation_note or "")[:120] or None,
                assigned_to_name=review.assigned_to_name,
                bounce_count=review.bounce_count,
            )
        )

    # Sort: tier desc (rojo first), then escalated_at asc (FIFO within tier)
    rows.sort(
        key=lambda r: (
            _TIER_ORDER.get(r.nivel.value if hasattr(r.nivel, "value") else str(r.nivel), 99),
            r.escalated_at or "",
        )
    )

    total = len(rows)
    start = page * page_size
    return Page(
        items=rows[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )
