"""get_claim_detail — fetch one claim and attach rules + ML/anomaly enrichment.

**Scoring strategy (double-scoring guard)**:
- If the claim already has ``alertas`` populated (i.e. it came from the
  synthetic dataset, where scores are baked at generation time), return it
  as-is without re-running the rules engine. Re-running ``score_claim`` via
  the context-poor ``RuleContext.from_claim`` path would clobber the rich
  demo scores because many signal flags (frequency, restrictive lists,
  similarity) can only be derived from the full DB context, not from
  ``ClaimDetail`` alone.
- If ``alertas`` is empty (un-scored DB claim, future path), run the live
  rules engine.

**ML / anomaly enrichment runs in BOTH branches** — synthetic pre-scored claims
still get ``ml_probability``, ``ml_factors``, ``anomaly_score``, and
``nearest_normal_claim_id`` filled in via ``enrich_claim_score`` when the
adapters are wired (artifacts present at boot). When adapters are absent the
fields stay at their defaults and the UI hides the corresponding widgets.

Returns None when the claim is not found (caller maps to 404).
"""

from __future__ import annotations

from datetime import datetime

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.domain.anomaly import AnomalyDetector
from app.domain.ml import FraudClassifier
from app.domain.rules.catalog import get_meta
from app.domain.rules.context import RuleContext
from app.infrastructure.reviews.ports import ReviewsStore
from app.schemas.claim import (
    ClaimAlert,
    ClaimDetail,
    ClaimReview,
    ClaimTimelineEvent,
    DictamenOutcome,
)
from app.schemas.risk import Tier
from app.use_cases.enrich_claim_score import enrich_claim_score
from app.use_cases.score_claim import score_claim


def _tier_to_severidad(tier: Tier) -> str:
    """Map a rule tier_hint to the UI severidad literal."""
    return {"rojo": "high", "amarillo": "med", "verde": "low"}[tier.value]


def _fmt_dt(value: datetime | None) -> str:
    """Render a datetime as YYYY-MM-DD HH:MM for the timeline label."""
    if value is None:
        return ""
    return value.strftime("%Y-%m-%d %H:%M")


_DICTAMEN_LABEL = {
    DictamenOutcome.confirmado_sospecha: "Dictamen: sospecha confirmada",
    DictamenOutcome.descartado: "Dictamen: descartado",
    DictamenOutcome.requiere_mas_info: "Dictamen: requiere más información",
}


def _workflow_timeline_events(review: ClaimReview) -> list[ClaimTimelineEvent]:
    """Build timeline entries from the workflow audit trail (escalado / take / dictamen / close)."""
    events: list[ClaimTimelineEvent] = []
    if review.escalated_at is not None:
        actor = review.escalated_by_name or "Analista"
        events.append(
            ClaimTimelineEvent(
                date=_fmt_dt(review.escalated_at),
                title="Escalado a Unidad Antifraude",
                tone="danger",
                desc=(
                    f"{actor}"
                    + (f" · «{review.escalation_note}»" if review.escalation_note else "")
                ),
            )
        )
    if review.taken_at is not None:
        actor = review.assigned_to_name or "Antifraude"
        events.append(
            ClaimTimelineEvent(
                date=_fmt_dt(review.taken_at),
                title="Tomado por Unidad Antifraude",
                tone="warn",
                desc=actor,
            )
        )
    if review.dictaminado_at is not None and review.dictamen_outcome is not None:
        actor = review.dictaminado_by_name or "Antifraude"
        events.append(
            ClaimTimelineEvent(
                date=_fmt_dt(review.dictaminado_at),
                title=_DICTAMEN_LABEL.get(review.dictamen_outcome, "Dictamen emitido"),
                tone=(
                    "danger"
                    if review.dictamen_outcome == DictamenOutcome.confirmado_sospecha
                    else "ok"
                ),
                desc=(
                    f"{actor}"
                    + (
                        f" · «{review.dictamen_justificacion}»"
                        if review.dictamen_justificacion
                        else ""
                    )
                ),
            )
        )
    if review.closed_at is not None:
        actor = review.closed_by_name or "Analista"
        events.append(
            ClaimTimelineEvent(
                date=_fmt_dt(review.closed_at),
                title="Cerrado sin escalar",
                tone="ok",
                desc=(
                    f"{actor}"
                    + (f" · «{review.closed_note}»" if review.closed_note else "")
                ),
            )
        )
    return events


async def get_claim_detail(
    queries: ClaimQueries,
    claim_id: str,
    *,
    reviews_store: ReviewsStore | None = None,
    classifier: FraudClassifier | None = None,
    detector: AnomalyDetector | None = None,
) -> ClaimDetail | None:
    """Return a ClaimDetail with score/nivel/alertas + ML enrichment, or None if not found.

    Claims already scored at generation time (non-empty ``alertas``) are
    returned as-is from the rules side (double-scoring guard). Un-scored
    claims are scored live via the rules engine. Both branches feed through
    ``enrich_claim_score`` so ML/anomaly fields are populated regardless of
    whether the rules were baked or live.

    When *reviews_store* is provided the live ``ClaimReview`` is attached so the
    detail page always reflects the current workflow state (§6 V2.6 §10 contract).
    """
    claim = await queries.get_detail(claim_id)
    if claim is None:
        return None

    if claim.alertas:
        # Pre-scored claim: keep rules side as-is; just attach the live review.
        if reviews_store is not None:
            live_review = await reviews_store.get(claim_id)
            claim = claim.model_copy(update={"review": live_review})
    else:
        # Live-scoring path for un-scored DB claims (post-hackathon).
        ctx = RuleContext.from_claim(claim)
        risk = score_claim(claim, ctx=ctx)

        alertas: list[ClaimAlert] = []
        for activation in risk.activations:
            meta = get_meta(activation.code)
            detalle = meta.short_description if meta is not None else activation.code
            severidad = _tier_to_severidad(activation.tier_hint)
            alertas.append(
                ClaimAlert(
                    code=activation.code,
                    puntos=activation.points,
                    severidad=severidad,
                    detalle=detalle,
                )
            )

        updates: dict[str, object] = {
            "score": risk.score,
            "nivel": risk.tier,
            "alertas": alertas,
            "similar": risk.similar,
        }
        if reviews_store is not None:
            updates["review"] = await reviews_store.get(claim_id)
        claim = claim.model_copy(update=updates)

    # Append workflow events (escalado / take / dictamen / close) so the
    # "Línea de tiempo del caso" tells the full story alongside Ocurrencia +
    # Reporte. The base timeline from _mapping already carries the source-date
    # events; we just extend it from the live review.
    workflow_events = _workflow_timeline_events(claim.review)
    if workflow_events:
        claim = claim.model_copy(
            update={"timeline": [*claim.timeline, *workflow_events]}
        )

    # ML + anomaly enrichment — runs in BOTH branches. Pass-through when ports unwired.
    return await enrich_claim_score(claim, classifier=classifier, detector=detector)
