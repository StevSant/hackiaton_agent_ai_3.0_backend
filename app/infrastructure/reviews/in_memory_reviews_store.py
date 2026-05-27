"""Process-singleton in-memory reviews store.

Holds ``dict[claim_id, ClaimReview]``.  The AsyncSession-backed
``ClaimReviewsRepo`` (app/repositories/claim_reviews_repo.py) is the future DB
path — leave it in place; just do not depend on a live DB here.

Seeds 3 claims at construction so the bandeja/histórico aren't empty at demo
start (per §6 V2.6 acceptance criteria).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.claim import ClaimReview, DictamenOutcome, ReviewStatus


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _seed_reviews() -> dict[str, ClaimReview]:
    """Return 2 escalado + 1 dictaminado seed rows for the antifraude inbox."""
    base_ts = datetime(2026, 5, 27, 8, 0, 0, tzinfo=UTC)
    return {
        # Seed 1: escalado, waiting to be taken
        "__SEED_001__": ClaimReview(
            status=ReviewStatus.escalado,
            escalated_by="seed-analista-1",
            escalated_by_name="Ana Seed",
            escalated_at=base_ts,
            escalation_note="Monto inusualmente alto y documentos incompletos.",
        ),
        # Seed 2: escalado, higher priority (rojo tier assumed by inbox sort)
        "__SEED_002__": ClaimReview(
            status=ReviewStatus.escalado,
            escalated_by="seed-analista-1",
            escalated_by_name="Ana Seed",
            escalated_at=datetime(2026, 5, 27, 9, 30, 0, tzinfo=UTC),
            escalation_note="Cobertura PTxRB — verificar RF-01.",
        ),
        # Seed 3: already dictaminado — visible in histórico
        "__SEED_003__": ClaimReview(
            status=ReviewStatus.dictaminado,
            escalated_by="seed-analista-2",
            escalated_by_name="Ana Seed 2",
            escalated_at=datetime(2026, 5, 26, 14, 0, 0, tzinfo=UTC),
            escalation_note="Dinámica del accidente inconsistente.",
            assigned_to="seed-antifraude-1",
            assigned_to_name="Lucía Seed",
            taken_at=datetime(2026, 5, 26, 15, 0, 0, tzinfo=UTC),
            dictamen_outcome=DictamenOutcome.confirmado_sospecha,
            dictamen_justificacion=(
                "Narrativa idéntica a caso __SEED_001__ y documentos de taller "
                "con fecha anterior al siniestro. Se confirma alerta de posible fraude."
            ),
            dictaminado_by="seed-antifraude-1",
            dictaminado_by_name="Lucía Seed",
            dictaminado_at=datetime(2026, 5, 26, 16, 30, 0, tzinfo=UTC),
        ),
    }


class InMemoryReviewsStore:
    """Process-singleton holding ClaimReview objects keyed by claim_id.

    Thread safety: sufficient for the hackathon's single-process server.
    """

    def __init__(self, *, seed: bool = True) -> None:
        self._store: dict[str, ClaimReview] = _seed_reviews() if seed else {}

    def get(self, claim_id: str) -> ClaimReview:
        """Return the review for *claim_id*, creating a fresh pendiente row if absent."""
        if claim_id not in self._store:
            self._store[claim_id] = ClaimReview()
        return self._store[claim_id]

    def save(self, claim_id: str, review: ClaimReview) -> ClaimReview:
        """Persist (upsert) a review and return it."""
        self._store[claim_id] = review
        return review

    def list_all(self) -> list[tuple[str, ClaimReview]]:
        """Return all (claim_id, review) pairs."""
        return list(self._store.items())

    def list_by_status(self, *statuses: ReviewStatus) -> list[tuple[str, ClaimReview]]:
        """Return (claim_id, review) pairs where status is in *statuses*."""
        status_set = set(statuses)
        return [(cid, rv) for cid, rv in self._store.items() if rv.status in status_set]

    def list_dictaminado_by(self, user_id: str) -> list[tuple[str, ClaimReview]]:
        """Return (claim_id, review) pairs dictaminado by *user_id*."""
        return [
            (cid, rv)
            for cid, rv in self._store.items()
            if rv.status == ReviewStatus.dictaminado and rv.dictaminado_by == user_id
        ]

    def list_closed_by(self, user_id: str) -> list[tuple[str, ClaimReview]]:
        """Return (claim_id, review) pairs closed (revisado_sin_escalar or dictaminado) by analista.

        For the analista histórico: includes claims SHE escalated that are now dictaminado,
        plus claims she closed directly (revisado_sin_escalar).
        """
        return [
            (cid, rv)
            for cid, rv in self._store.items()
            if (
                rv.status == ReviewStatus.revisado_sin_escalar and rv.closed_by == user_id
            )
            or (rv.status == ReviewStatus.dictaminado and rv.escalated_by == user_id)
        ]
