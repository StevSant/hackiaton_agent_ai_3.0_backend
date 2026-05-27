"""Repository for `claim_reviews` — workflow audit trail.

PK is `claim_id` (1:1). The row is created lazily on first status transition.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.claim_review import ClaimReview


class ClaimReviewsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_claim_id(self, claim_id: str) -> ClaimReview | None:
        return await self._s.get(ClaimReview, claim_id)

    async def upsert(self, review: ClaimReview) -> ClaimReview:
        merged: ClaimReview = await self._s.merge(review)
        await self._s.flush()
        return merged
