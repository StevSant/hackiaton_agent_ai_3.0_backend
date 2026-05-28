"""take_claim — antifraude transitions escalado → en_revision."""

from __future__ import annotations

from app.domain.auth.user import User
from app.domain.reviews.state_machine import (
    ConflictError,
    ReviewTransitionError,
    apply_take,
)
from app.infrastructure.reviews.ports import ReviewsStore
from app.schemas.claim import ClaimReview, ReviewStatus


async def take_claim(
    store: ReviewsStore,
    claim_id: str,
    *,
    user: User,
) -> tuple[ClaimReview, bool]:
    """Apply escalado → en_revision for *claim_id*.

    Returns ``(review, already_taken_by_same_user)``.
    - already_taken == True  → idempotent (same user re-calling) → return 200 with current state.
    - already_taken == False → fresh take.

    Raises ``ReviewTransitionError`` for wrong state.
    Raises ``ConflictError`` when a *different* antifraude already took it.
    """
    review = await store.get(claim_id)

    # Idempotency: same user + already en_revision
    if review.status == ReviewStatus.en_revision and review.assigned_to == str(user.id):
        return review, True

    # Different user trying to take an en_revision claim
    if review.status == ReviewStatus.en_revision and review.assigned_to != str(user.id):
        raise ConflictError(review.assigned_to or "")

    try:
        updated, was_idempotent = apply_take(review, by_id=str(user.id), by_name=user.full_name)
    except (ReviewTransitionError, ConflictError):
        raise
    saved = await store.save(claim_id, updated)
    return saved, was_idempotent
