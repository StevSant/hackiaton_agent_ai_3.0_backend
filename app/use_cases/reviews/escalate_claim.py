"""escalate_claim — analista transitions pendiente → escalado."""

from __future__ import annotations

from app.domain.auth.user import User
from app.domain.reviews.state_machine import ReviewTransitionError, apply_escalate
from app.infrastructure.reviews.in_memory_reviews_store import InMemoryReviewsStore
from app.schemas.claim import ClaimReview


def escalate_claim(
    store: InMemoryReviewsStore,
    claim_id: str,
    *,
    user: User,
    note: str | None = None,
) -> ClaimReview:
    """Apply pendiente → escalado transition for *claim_id*.

    Raises ``ReviewTransitionError`` when the current state doesn't allow escalation.
    """
    review = store.get(claim_id)
    try:
        updated = apply_escalate(review, by_id=str(user.id), by_name=user.full_name, note=note)
    except ReviewTransitionError:
        raise
    return store.save(claim_id, updated)
