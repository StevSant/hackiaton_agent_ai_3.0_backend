"""auto_escalate_rojo — escalate a claim automatically when scored as rojo.

The claim moves pendiente → escalado with a "system" attribution. No-ops if the
claim is not rojo or if its review is already past pendiente (already
escalated, in_revision, dictaminado, or revisado_sin_escalar).
"""

from __future__ import annotations

from app.domain.reviews.state_machine import ReviewTransitionError, apply_escalate
from app.infrastructure.reviews.ports import ReviewsStore
from app.schemas.claim import ClaimReview, ReviewStatus
from app.schemas.risk import Tier

SYSTEM_ACTOR_ID = "system"
SYSTEM_ACTOR_NAME = "Sistema (auto)"
SYSTEM_NOTE_TEMPLATE = "Escalación automática: score {score}/100 (rojo)."


async def auto_escalate_rojo(
    store: ReviewsStore,
    claim_id: str,
    *,
    tier: Tier,
    score: int,
) -> ClaimReview | None:
    """Apply pendiente → escalado for rojo claims still in pendiente state.

    Returns the saved review when escalation happened, or None when nothing was
    done (claim wasn't rojo, or its review already moved past pendiente).
    """
    if tier != Tier.rojo:
        return None

    review = await store.get(claim_id)
    if review.status != ReviewStatus.pendiente:
        return None

    try:
        updated = apply_escalate(
            review,
            by_id=SYSTEM_ACTOR_ID,
            by_name=SYSTEM_ACTOR_NAME,
            note=SYSTEM_NOTE_TEMPLATE.format(score=score),
        )
    except ReviewTransitionError:
        # Defensive: we already checked the status above, so this shouldn't fire
        # except in race-condition territory. Treat as a no-op.
        return None

    return await store.save(claim_id, updated)
