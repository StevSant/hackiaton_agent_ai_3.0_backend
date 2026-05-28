"""In-memory ``ReviewsStore`` — kept for unit / smoke tests only.

Production code uses :class:`DbReviewsStore` (Postgres-backed). This adapter is
async to satisfy the :class:`ReviewsStore` protocol; the awaits resolve
synchronously.
"""

from __future__ import annotations

from app.schemas.claim import ClaimReview, ReviewStatus


class InMemoryReviewsStore:
    """Process-local dict implementing the ``ReviewsStore`` protocol.

    Thread safety: sufficient for single-process tests.
    """

    def __init__(self) -> None:
        self._store: dict[str, ClaimReview] = {}

    async def get(self, claim_id: str) -> ClaimReview:
        if claim_id not in self._store:
            self._store[claim_id] = ClaimReview()
        return self._store[claim_id]

    async def save(self, claim_id: str, review: ClaimReview) -> ClaimReview:
        self._store[claim_id] = review
        return review

    async def list_all(self) -> list[tuple[str, ClaimReview]]:
        return list(self._store.items())

    async def list_by_status(
        self, *statuses: ReviewStatus
    ) -> list[tuple[str, ClaimReview]]:
        status_set = set(statuses)
        return [(cid, rv) for cid, rv in self._store.items() if rv.status in status_set]

    async def list_dictaminado_by(
        self, user_id: str
    ) -> list[tuple[str, ClaimReview]]:
        return [
            (cid, rv)
            for cid, rv in self._store.items()
            if rv.status == ReviewStatus.dictaminado and rv.dictaminado_by == user_id
        ]

    async def list_closed_by(self, user_id: str) -> list[tuple[str, ClaimReview]]:
        return [
            (cid, rv)
            for cid, rv in self._store.items()
            if (
                rv.status == ReviewStatus.revisado_sin_escalar and rv.closed_by == user_id
            )
            or (rv.status == ReviewStatus.dictaminado and rv.escalated_by == user_id)
        ]
