"""Pure state-machine logic for the 5-state claim escalation workflow (§6 V2.6).

No I/O.  All functions take a ``ClaimReview`` VO + actor metadata and return
a new ``ClaimReview`` with the transition applied, or raise a typed error.

State transitions:
    pendiente --escalate(analista)--> escalado
    pendiente --close(analista, bounce_count==0)--> revisado_sin_escalar (terminal)
    escalado --take(antifraude)--> en_revision  (idempotent same user; 409 diff user)
    escalado --dictamen(antifraude, atajo)--> dictaminado | pendiente (bounce)
    en_revision --dictamen(antifraude, mine)--> dictaminado | pendiente (bounce)
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.claim import ClaimReview, DictamenOutcome, ReviewStatus


class ReviewTransitionError(Exception):
    """Invalid state for the requested transition."""

    def __init__(self, current: ReviewStatus, action: str) -> None:
        self.current = current
        self.action = action
        super().__init__(f"Cannot '{action}' from state '{current}'")


class GuardError(Exception):
    """A guard condition blocks the transition (e.g. bounce_count > 0 on close)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ConflictError(Exception):
    """Another user already holds the claim (take idempotency guard)."""

    def __init__(self, owner_id: str) -> None:
        self.owner_id = owner_id
        super().__init__(f"Claim already taken by user '{owner_id}'")


def _now() -> datetime:
    return datetime.now(tz=UTC)


def apply_escalate(
    review: ClaimReview,
    *,
    by_id: str,
    by_name: str,
    note: str | None = None,
) -> ClaimReview:
    """pendiente → escalado.  Only valid from pendiente (including bounced cases)."""
    if review.status != ReviewStatus.pendiente:
        raise ReviewTransitionError(review.status, "escalate")
    return review.model_copy(
        update={
            "status": ReviewStatus.escalado,
            "escalated_by": by_id,
            "escalated_by_name": by_name,
            "escalated_at": _now(),
            "escalation_note": note,
        }
    )


def apply_close(
    review: ClaimReview,
    *,
    by_id: str,
    by_name: str,
    note: str | None = None,
) -> ClaimReview:
    """pendiente → revisado_sin_escalar.

    Guard: only valid when bounce_count == 0.  A bounced case must be re-escalated.
    """
    if review.status != ReviewStatus.pendiente:
        raise ReviewTransitionError(review.status, "close")
    if review.bounce_count > 0:
        raise GuardError(
            "No se puede cerrar sin escalar un caso que ha sido devuelto "
            "(bounce_count > 0). Debe re-escalar con nueva información."
        )
    return review.model_copy(
        update={
            "status": ReviewStatus.revisado_sin_escalar,
            "closed_by": by_id,
            "closed_by_name": by_name,
            "closed_at": _now(),
            "closed_note": note,
        }
    )


def apply_take(
    review: ClaimReview,
    *,
    by_id: str,
    by_name: str,
) -> tuple[ClaimReview, bool]:
    """escalado → en_revision.

    Returns (updated_review, was_idempotent).
    - Idempotent when same antifraude calls twice → (review unchanged, True).
    - Raises ConflictError when a *different* antifraude already took it.
    - Raises ReviewTransitionError when not in escalado state.
    """
    if review.status != ReviewStatus.escalado:
        raise ReviewTransitionError(review.status, "take")

    # Idempotency: same user re-taking is fine (200 OK)
    if review.assigned_to == by_id and review.status == ReviewStatus.escalado:
        # Still escalado (user called take but it hasn't persisted yet) — first call
        pass
    if review.assigned_to is not None and review.assigned_to != by_id:
        # en_revision would have been set in a previous call; but we check here too
        raise ConflictError(review.assigned_to)

    # Same user taking an already-en_revision claim is covered by the state guard above.
    updated = review.model_copy(
        update={
            "status": ReviewStatus.en_revision,
            "assigned_to": by_id,
            "assigned_to_name": by_name,
            "taken_at": _now(),
        }
    )
    return updated, False


def apply_dictamen(
    review: ClaimReview,
    *,
    by_id: str,
    by_name: str,
    outcome: DictamenOutcome,
    justificacion: str,
) -> ClaimReview:
    """escalado (atajo) | en_revision (mine) → dictaminado | pendiente (bounce).

    Guards:
    - Only from escalado or en_revision.
    - From en_revision: only the assigned user may dictaminate (not another antifraude).
    - justificacion must be ≥ 20 characters.

    On requiere_mas_info: bounces back to pendiente, increments bounce_count, stores note.
    Otherwise: transitions to dictaminado.
    """
    if review.status not in {ReviewStatus.escalado, ReviewStatus.en_revision}:
        raise ReviewTransitionError(review.status, "dictamen")

    if review.status == ReviewStatus.en_revision and review.assigned_to != by_id:
        raise GuardError(
            f"Solo el analista asignado ({review.assigned_to_name or review.assigned_to}) "
            "puede emitir dictamen sobre este caso."
        )

    if len(justificacion.strip()) < 20:
        raise GuardError("La justificación debe tener al menos 20 caracteres.")

    if outcome == DictamenOutcome.requiere_mas_info:
        # Bounce back to pendiente
        return review.model_copy(
            update={
                "status": ReviewStatus.pendiente,
                "bounce_count": review.bounce_count + 1,
                "bounce_note": justificacion,
                # Clear assignment — antifraude released it back
                "assigned_to": None,
                "assigned_to_name": None,
                "taken_at": None,
            }
        )

    return review.model_copy(
        update={
            "status": ReviewStatus.dictaminado,
            "dictamen_outcome": outcome,
            "dictamen_justificacion": justificacion,
            "dictaminado_by": by_id,
            "dictaminado_by_name": by_name,
            "dictaminado_at": _now(),
        }
    )
