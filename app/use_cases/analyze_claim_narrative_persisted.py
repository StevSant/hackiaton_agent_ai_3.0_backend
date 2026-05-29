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
from app.domain.auth.user import User
from app.domain.ml import FraudClassifier
from app.domain.similarity import NarrativeSimilarity
from app.domain.vehicle_identity import VehicleDecoder
from app.infrastructure.audit import AuditStore
from app.infrastructure.db.models.siniestro import Siniestro
from app.infrastructure.llm.ports import LLMProvider
from app.schemas.audit import AuditAction, AuditActor
from app.schemas.claim import ClaimDetail
from app.schemas.narrative_analysis import NarrativeAnalysis
from app.use_cases._rescore_one import rescore_one
from app.use_cases.analyze_claim_narrative import analyze_claim_narrative
from app.use_cases.emit_audit_event import emit_audit_event
from app.use_cases.enrich_claim_score import enrich_claim_score
from app.use_cases.hydrate_claim_detail import hydrate_claim_detail

logger = logging.getLogger(__name__)

# Narratives shorter than this carry no analyzable content (matches the
# similarity layer's floor in score_claim_from_db._enrich_similarity).
_MIN_DESCRIPCION_LEN = 30

# Resumen text for the fallback analyses. We ALWAYS persist a NarrativeAnalysis so
# the detail card resolves — leaving it null traps the UI in "análisis en curso".
_RESUMEN_TOO_SHORT = (
    "La narrativa registrada es demasiado breve para un análisis NLP detallado."
)
_RESUMEN_LLM_FAILED = (
    "No se pudo completar el análisis automático de la narrativa. "
    'Pulsá «Re-analizar caso» para reintentar.'
)


def _fallback_analysis(resumen: str) -> NarrativeAnalysis:
    """A coherent, content-free analysis used when the LLM can't or shouldn't run.

    `narrativa_ilogica=False` keeps FS-09 in its default (no-signal) state — same
    as having no analysis at all — but the populated object lets the UI render a
    resolved card with an honest note instead of an eternal spinner."""
    return NarrativeAnalysis(narrativa_ilogica=False, resumen_narrativa=resumen)


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
    audit: AuditStore | None = None,
    user: User | None = None,
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
    if cached and not force:
        # Already analyzed — return the claim enriched with ML/anomaly, no LLM call.
        return await enrich_claim_score(detail, classifier=classifier, detector=detector)

    # Decide the analysis to persist. We ALWAYS end up with a non-null analysis so
    # the UI never sticks on "en curso": a real LLM read when the narrative is long
    # enough, a fallback note otherwise (too short, or the LLM call failed).
    analyzable = bool(detail.descripcion) and len(detail.descripcion) >= _MIN_DESCRIPCION_LEN
    ran_llm = False
    if not analyzable:
        analysis = _fallback_analysis(_RESUMEN_TOO_SHORT)
    else:
        try:
            analysis = await analyze_claim_narrative(
                detail.descripcion, llm=llm, llm_model=llm_model
            )
            ran_llm = True
        except Exception:  # LLM down / bad JSON / schema mismatch — never 500 the view.
            logger.exception("narrative: analysis failed for %s; persisting fallback", claim_id)
            analysis = _fallback_analysis(_RESUMEN_LLM_FAILED)

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

    # Audit only a genuine LLM run (cache hits return above; fallbacks aren't an
    # "analysis"). Best-effort; the analysis is already committed.
    if ran_llm and audit is not None and user is not None:
        try:
            await emit_audit_event(
                audit,
                user=user,
                action=AuditAction.analisis_narrativa,
                actor=AuditActor.agente,
                title="Analizó la narrativa del caso",
                detail=(
                    "Relato incoherente detectado"
                    if analysis.narrativa_ilogica
                    else "Relato coherente"
                ),
                target=claim_id,
            )
        except Exception:  # auditing is best-effort
            logger.exception("narrative: failed to audit analysis for %s", claim_id)

    return await enrich_claim_score(scored, classifier=classifier, detector=detector)
