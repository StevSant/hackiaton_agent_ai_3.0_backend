"""close_claim — analista transitions pendiente → revisado_sin_escalar."""

from __future__ import annotations

from app.domain.auth.user import User
from app.domain.reviews.state_machine import GuardError, ReviewTransitionError, apply_close
from app.infrastructure.reviews.in_memory_reviews_store import InMemoryReviewsStore
from app.schemas.claim import ClaimReview


def close_claim(
    store: InMemoryReviewsStore,
    claim_id: str,
    *,
    user: User,
    note: str | None = None,
) -> ClaimReview:
    """Apply pendiente → revisado_sin_escalar transition.

    Raises ``ReviewTransitionError`` for wrong state.
    Raises ``GuardError`` when bounce_count > 0.
    """
    review = store.get(claim_id)
    try:
        updated = apply_close(review, by_id=str(user.id), by_name=user.full_name, note=note)
    except (ReviewTransitionError, GuardError):
        raise
    return store.save(claim_id, updated)
