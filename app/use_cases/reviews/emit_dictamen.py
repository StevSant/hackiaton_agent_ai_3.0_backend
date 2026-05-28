"""emit_dictamen — antifraude emits a decision (dictamen) on a claim."""

from __future__ import annotations

from app.domain.auth.user import User
from app.domain.reviews.state_machine import GuardError, ReviewTransitionError, apply_dictamen
from app.infrastructure.reviews.ports import ReviewsStore
from app.schemas.claim import ClaimReview, DictamenOutcome


async def emit_dictamen(
    store: ReviewsStore,
    claim_id: str,
    *,
    user: User,
    outcome: DictamenOutcome,
    justificacion: str,
) -> ClaimReview:
    """Apply dictamen transition: escalado|en_revision → dictaminado | pendiente (bounce).

    Raises ``ReviewTransitionError`` for wrong source state.
    Raises ``GuardError`` for guard violations (wrong assignee, short justificacion).
    """
    review = await store.get(claim_id)
    try:
        updated = apply_dictamen(
            review,
            by_id=str(user.id),
            by_name=user.full_name,
            outcome=outcome,
            justificacion=justificacion,
        )
    except (ReviewTransitionError, GuardError):
        raise
    return await store.save(claim_id, updated)
