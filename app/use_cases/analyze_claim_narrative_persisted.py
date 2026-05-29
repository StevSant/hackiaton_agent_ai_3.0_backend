"""analyze_claim_narrative_persisted — on-demand NLP analysis, cached in the DB.

The engine behind ``POST /claims/{id}/narrative-analysis``. Runs the LLM narrative
analyzer once, writes the ``narrativa_ilogica`` verdict back into
``siniestros.signals`` (so FS-09 fires from real NLP), then re-scores the claim
through the shared ``rescore_one`` core — persisting both the fresh score and the
``narrative_analysis`` cache on ``claim_scores`` in one committed transaction.

On a second call the cached analysis is returned without touching the LLM.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.anomaly import AnomalyDetector
from app.domain.ml import FraudClassifier
from app.domain.similarity import NarrativeSimilarity
from app.domain.vehicle_identity import VehicleDecoder
from app.infrastructure.db.models.siniestro import Siniestro
from app.infrastructure.llm.ports import LLMProvider
from app.schemas.claim import ClaimDetail
from app.use_cases._rescore_one import rescore_one
from app.use_cases.analyze_claim_narrative import analyze_claim_narrative
from app.use_cases.enrich_claim_score import enrich_claim_score
from app.use_cases.hydrate_claim_detail import hydrate_claim_detail

logger = logging.getLogger(__name__)

# Narratives shorter than this carry no analyzable content (matches the
# similarity layer's floor in score_claim_from_db._enrich_similarity).
_MIN_DESCRIPCION_LEN = 30


async def analyze_claim_narrative_persisted(
    session: AsyncSession,
    claim_id: str,
    *,
    llm: LLMProvider,
    llm_model: str,
    force: bool = False,
    similarity: NarrativeSimilarity | None = None,
    classifier: FraudClassifier | None = None,
    detector: AnomalyDetector | None = None,
    decoder: VehicleDecoder | None = None,
) -> ClaimDetail | None:
    """Analyze a claim's narrative, cache it, and re-score from the fresh verdict.

    Args:
        session:    AsyncSession (committed here on success).
        claim_id:   The ``siniestros.id_siniestro`` to analyze.
        llm:        LLMProvider for the structured analysis call.
        llm_model:  Model identifier from settings.
        force:      Re-run the analyzer even when a cached result exists.
        similarity: NarrativeSimilarity port; passed through to rescore.
        classifier: Supervised fraud classifier; ML fields left default when None.
        detector:   Anomaly detector; anomaly fields left default when None.
        decoder:    VehicleDecoder port; FS-15 check skipped when None.

    Returns:
        The updated ClaimDetail (with ``narrative_analysis`` populated and FS-09
        reflecting the verdict), or None when the claim does not exist.
    """
    sin: Siniestro | None = await session.get(Siniestro, claim_id)
    if sin is None:
        return None

    detail = await hydrate_claim_detail(session, sin)

    cached = detail.narrative_analysis is not None
    analyzable = bool(detail.descripcion) and len(detail.descripcion) >= _MIN_DESCRIPCION_LEN
    if (cached and not force) or not analyzable:
        # Nothing to (re)compute — return the claim enriched with ML/anomaly.
        return await enrich_claim_score(detail, classifier=classifier, detector=detector)

    analysis = await analyze_claim_narrative(
        detail.descripcion, llm=llm, llm_model=llm_model
    )

    # Write the coherence verdict back into signals so FS-09 fires from real NLP.
    # Reassign (not in-place mutate) so SQLAlchemy tracks the JSONB change.
    sin.signals = {
        **(sin.signals or {}),
        "narrativa_ilogica": analysis.narrativa_ilogica,
    }

    # Carry the analysis on the detail so rescore_one persists it to claim_scores.
    detail = detail.model_copy(update={"narrative_analysis": analysis})

    scored, _risk = await rescore_one(
        session, detail, similarity=similarity, decoder=decoder
    )
    # NOTE: no auto-escalation here. Narrative analysis runs lazily on first VIEW
    # of a claim; viewing must never mutate workflow state. Auto-escalation of
    # rojos happens at import / explicit rescore, not on read.
    await session.commit()

    return await enrich_claim_score(scored, classifier=classifier, detector=detector)
