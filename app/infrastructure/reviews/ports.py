"""Port for the reviews store.

Both ``InMemoryReviewsStore`` (tests) and ``DbReviewsStore`` (production —
backed by Postgres via ``ClaimReviewsRepo``) implement this Protocol.
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.claim import ClaimReview, ReviewStatus


class ReviewsStore(Protocol):
    """Async store for :class:`ClaimReview` rows keyed by ``claim_id``."""

    async def get(self, claim_id: str) -> ClaimReview:
        """Return the review for *claim_id*, creating a fresh pendiente row if absent."""
        ...

    async def save(self, claim_id: str, review: ClaimReview) -> ClaimReview:
        """Persist (upsert) a review and return it."""
        ...

    async def list_all(self) -> list[tuple[str, ClaimReview]]:
        """Return all (claim_id, review) pairs."""
        ...

    async def list_by_status(
        self, *statuses: ReviewStatus
    ) -> list[tuple[str, ClaimReview]]:
        """Return (claim_id, review) pairs whose status is in *statuses*."""
        ...

    async def list_dictaminado_by(
        self, user_id: str
    ) -> list[tuple[str, ClaimReview]]:
        """Return (claim_id, review) pairs dictaminado by *user_id*."""
        ...

    async def list_closed_by(self, user_id: str) -> list[tuple[str, ClaimReview]]:
        """Return (claim_id, review) pairs closed by analista *user_id*.

        Includes claims SHE escalated that are now dictaminado, plus claims she
        closed directly (revisado_sin_escalar).
        """
        ...
