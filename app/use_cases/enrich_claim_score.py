"""enrich_claim_score — second-stage enricher: ML probability + anomaly score.

The rules engine (``score_claim``) is pure synchronous and deliberately untouched
by ML: explainability requires that the analyst sees rules and the model
*independently* (challenge spec §2.4, "Explicabilidad y Ética" — 25% of grade).

This use case runs AFTER ``score_claim`` (or after the double-scoring guard in
``get_claim_detail`` for pre-scored synthetic claims) and populates the ML /
anomaly fields on the returned ``ClaimDetail``. When neither port is wired
(artifacts absent at boot) the claim passes through unchanged.

Why a separate use case rather than folding into score_claim:
  - score_claim stays sync / deterministic — easy to unit-test rule-by-rule
  - The wire score remains "rules only" — model can drift independently
  - The graceful "no models loaded" path keeps the demo bootable without LGBM
"""

from __future__ import annotations

import asyncio

from app.domain.anomaly import AnomalyDetector
from app.domain.ml import FraudClassifier, extract_features
from app.domain.rules.context import RuleContext
from app.schemas.claim import ClaimDetail


async def enrich_claim_score(
    claim: ClaimDetail,
    *,
    classifier: FraudClassifier | None,
    detector: AnomalyDetector | None,
) -> ClaimDetail:
    """Return *claim* with ML / anomaly fields populated when ports are wired.

    Args:
        claim:      Already-scored claim (post-rules engine).
        classifier: Supervised fraud classifier or None. None → ml fields left at default.
        detector:   Anomaly detector or None. None → anomaly fields left at default.

    Returns:
        A new ``ClaimDetail`` with ``ml_probability``, ``ml_factors``,
        ``anomaly_score``, and ``nearest_normal_claim_id`` filled in where the
        corresponding port was provided. Pass-through when both ports are None.
    """
    if classifier is None and detector is None:
        return claim

    ctx = RuleContext.from_claim(claim)
    features = extract_features(claim, ctx)

    ml_task = classifier.predict(features) if classifier is not None else None
    anomaly_task = detector.score(features) if detector is not None else None

    ml_result, anomaly_result = await asyncio.gather(
        ml_task if ml_task is not None else _none(),
        anomaly_task if anomaly_task is not None else _none(),
    )

    updates: dict[str, object] = {}
    if ml_result is not None:
        updates["ml_probability"] = ml_result.probability
        updates["ml_factors"] = ml_result.factors
    if anomaly_result is not None:
        updates["anomaly_score"] = anomaly_result.score
        updates["nearest_normal_claim_id"] = anomaly_result.nearest_normal_claim_id

    return claim.model_copy(update=updates) if updates else claim


async def _none() -> None:
    """Awaitable that resolves to None — fills the unused slot in asyncio.gather."""
    return None
