"""Postgres-backed reviews store.

Wraps :class:`ClaimReviewsRepo` so the rest of the codebase can use a single
``ReviewsStore`` protocol regardless of whether persistence is in-memory or DB.
This is the default in production (wired via :mod:`app.api.deps`); the
in-memory store is only used by unit/smoke tests.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.claim_review import ClaimReview as ClaimReviewRow
from app.repositories.claim_reviews_repo import ClaimReviewsRepo
from app.schemas.claim import ClaimReview, DictamenOutcome, ReviewStatus


class DbReviewsStore:
    """Async ``ReviewsStore`` backed by Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ClaimReviewsRepo(session)

    async def get(self, claim_id: str) -> ClaimReview:
        row = await self._repo.get_by_claim_id(claim_id)
        if row is None:
            return ClaimReview()
        return _row_to_schema(row)

    async def save(self, claim_id: str, review: ClaimReview) -> ClaimReview:
        row = _schema_to_row(claim_id, review)
        merged = await self._repo.upsert(row)
        await self._session.commit()
        return _row_to_schema(merged)

    async def list_all(self) -> list[tuple[str, ClaimReview]]:
        result = await self._session.execute(select(ClaimReviewRow))
        rows = result.scalars().all()
        return [(r.claim_id, _row_to_schema(r)) for r in rows]

    async def list_by_status(
        self, *statuses: ReviewStatus
    ) -> list[tuple[str, ClaimReview]]:
        if not statuses:
            return []
        values = [s.value for s in statuses]
        result = await self._session.execute(
            select(ClaimReviewRow).where(ClaimReviewRow.status.in_(values))
        )
        rows = result.scalars().all()
        return [(r.claim_id, _row_to_schema(r)) for r in rows]

    async def list_dictaminado_by(
        self, user_id: str
    ) -> list[tuple[str, ClaimReview]]:
        result = await self._session.execute(
            select(ClaimReviewRow).where(
                ClaimReviewRow.status == ReviewStatus.dictaminado.value,
                ClaimReviewRow.dictaminado_by == user_id,
            )
        )
        rows = result.scalars().all()
        return [(r.claim_id, _row_to_schema(r)) for r in rows]

    async def list_closed_by(self, user_id: str) -> list[tuple[str, ClaimReview]]:
        # Analista histórico: revisado_sin_escalar closed by them, OR
        # dictaminado claims they originally escalated.
        result = await self._session.execute(
            select(ClaimReviewRow).where(
                (
                    (ClaimReviewRow.status == ReviewStatus.revisado_sin_escalar.value)
                    & (ClaimReviewRow.closed_by == user_id)
                )
                | (
                    (ClaimReviewRow.status == ReviewStatus.dictaminado.value)
                    & (ClaimReviewRow.escalated_by == user_id)
                )
            )
        )
        rows = result.scalars().all()
        return [(r.claim_id, _row_to_schema(r)) for r in rows]


def _row_to_schema(row: ClaimReviewRow) -> ClaimReview:
    return ClaimReview(
        status=ReviewStatus(row.status),
        escalated_by=row.escalated_by,
        escalated_by_name=row.escalated_by_name,
        escalated_at=row.escalated_at,
        escalation_note=row.escalation_note,
        assigned_to=row.assigned_to,
        assigned_to_name=row.assigned_to_name,
        taken_at=row.taken_at,
        dictamen_outcome=(
            DictamenOutcome(row.dictamen_outcome)
            if row.dictamen_outcome is not None
            else None
        ),
        dictamen_justificacion=row.dictamen_justificacion,
        dictaminado_by=row.dictaminado_by,
        dictaminado_by_name=row.dictaminado_by_name,
        dictaminado_at=row.dictaminado_at,
        bounce_count=row.bounce_count,
        bounce_note=row.bounce_note,
        closed_by=row.closed_by,
        closed_by_name=row.closed_by_name,
        closed_at=row.closed_at,
        closed_note=row.closed_note,
    )


def _schema_to_row(claim_id: str, review: ClaimReview) -> ClaimReviewRow:
    return ClaimReviewRow(
        claim_id=claim_id,
        status=review.status.value,
        escalated_by=review.escalated_by,
        escalated_by_name=review.escalated_by_name,
        escalated_at=review.escalated_at,
        escalation_note=review.escalation_note,
        assigned_to=review.assigned_to,
        assigned_to_name=review.assigned_to_name,
        taken_at=review.taken_at,
        dictamen_outcome=(
            review.dictamen_outcome.value
            if review.dictamen_outcome is not None
            else None
        ),
        dictamen_justificacion=review.dictamen_justificacion,
        dictaminado_by=review.dictaminado_by,
        dictaminado_by_name=review.dictaminado_by_name,
        dictaminado_at=review.dictaminado_at,
        bounce_count=review.bounce_count,
        bounce_note=review.bounce_note,
        closed_by=review.closed_by,
        closed_by_name=review.closed_by_name,
        closed_at=review.closed_at,
        closed_note=review.closed_note,
    )
