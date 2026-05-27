"""list_claims — paginated, filtered list of ClaimSummary.

Reads via the ClaimQueries port so the implementation is adapter-agnostic
(in-memory today, DbClaimQueries once Miquel's repo lane lands).

Filter contract per design spec §10:
    ?tier=   verde|amarillo|rojo
    ?ramo=   free text (case-insensitive contains)
    ?from=   date ISO (fecha_ocurrencia >=)
    ?to=     date ISO (fecha_ocurrencia <=)
    ?status= ReviewStatus value
    ?q=      free text matched against id, asegurado, cobertura, ciudad
    ?page=   0-indexed page number (default 0)
    ?page_size= items per page (default 25, max 100)

Sorted by score desc before pagination.
"""

from __future__ import annotations

from datetime import date

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.schemas.claim import ClaimSummary, ReviewStatus
from app.schemas.page import Page
from app.schemas.risk import Tier


async def list_claims(
    queries: ClaimQueries,
    *,
    tier: Tier | None = None,
    ramo: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    status: ReviewStatus | None = None,
    q: str | None = None,
    page: int = 0,
    page_size: int = 25,
) -> Page[ClaimSummary]:
    """Return a paginated, filtered, score-sorted page of ClaimSummary."""
    # Fetch full list via the port (all tiers)
    all_summaries = await queries.list_top_risk(top_n=9999, tier="all")

    # --- filter pipeline ---
    items = all_summaries

    if tier is not None:
        items = [c for c in items if c.nivel == tier]

    if ramo is not None:
        ramo_lower = ramo.lower()
        items = [c for c in items if ramo_lower in c.ramo.lower()]

    if from_date is not None:
        items = [c for c in items if c.fecha_ocurrencia >= from_date]

    if to_date is not None:
        items = [c for c in items if c.fecha_ocurrencia <= to_date]

    if status is not None:
        items = [c for c in items if c.review_status == status]

    if q is not None:
        q_lower = q.lower()
        items = [
            c
            for c in items
            if q_lower in c.id.lower()
            or q_lower in c.asegurado.lower()
            or q_lower in c.cobertura.lower()
            or q_lower in c.ciudad.lower()
        ]

    # Already sorted by score desc from list_top_risk; re-sort to be safe after filter
    items = sorted(items, key=lambda c: c.score, reverse=True)

    total = len(items)
    start = page * page_size
    page_items = items[start : start + page_size]

    return Page(items=page_items, total=total, page=page, page_size=page_size)
