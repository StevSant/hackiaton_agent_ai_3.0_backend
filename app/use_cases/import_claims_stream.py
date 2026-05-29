"""stream_import_claims — async-generator use case for the SSE import endpoint.

Processes claims one at a time, yielding ``ImportStreamEvent`` instances as each
stage completes. Mirrors the sync ``import_claims`` use case but surfaces
intermediate state as a real-time stream so the UI renders a live progress view.

Enrichment beyond ``RuleContext.from_claim``:
- Provider / beneficiary restrictive-list check via the ``Proveedor`` table.
- Narrative similarity via pgvector (``NarrativeSimilarity`` port).
- Document inconsistency flags from documento.inconsistencia_detectada text.

ML + anomaly scores are computed when the respective adapters are provided;
gracefully skipped (no event emitted) when they are absent (e.g. no artifact).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.anomaly import AnomalyDetector
from app.domain.ml import FraudClassifier, extract_features
from app.domain.rules.catalog import all_rules, get_meta
from app.domain.rules.context import RuleContext
from app.domain.similarity import NarrativeSimilarity
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.claim import ClaimAlert, ClaimDetail
from app.schemas.imports.stream import (
    AnomalyDetectedData,
    AnomalyDetectedEvent,
    CaseCompletedData,
    CaseCompletedEvent,
    CaseStartedData,
    CaseStartedEvent,
    ImportCompletedData,
    ImportCompletedEvent,
    ImportErrorData,
    ImportErrorEvent,
    ImportStartedData,
    ImportStartedEvent,
    ImportStreamEvent,
    MLScoredData,
    MLScoredEvent,
    ParseRowData,
    ParseRowEvent,
    RuleHardFiredData,
    RuleHardFiredEvent,
    RuleScoringData,
    RuleScoringEvent,
    SimilarClaimRef,
    SimilarityFoundData,
    SimilarityFoundEvent,
)
from app.schemas.risk import SimilarClaim
from app.use_cases.claim_score_persist import claim_detail_to_score_row, upsert_claim_score
from app.use_cases.load_dataset._aggregates import compute_aggregates
from app.use_cases.load_dataset._mapping import (
    claim_detail_to_asegurado,
    claim_detail_to_documentos,
    claim_detail_to_poliza,
    claim_detail_to_proveedor,
    claim_detail_to_siniestro,
)

logger = logging.getLogger(__name__)

# Markers in document observation text that indicate document inconsistency / falsification
_INCONSISTENCY_MARKERS = frozenset(["adulterada", "alterada", "falsificada", "falsa", "inconsist"])
_FALSIFICATION_MARKERS = frozenset(["falsificada", "falsa", "adulterada"])

# Hard rules are prefixed with RF-; scored signals with FS-
_HARD_RULE_PREFIX = "RF-"


async def stream_import_claims(
    records: list[ClaimDetail],
    filename: str,
    session: AsyncSession | None,
    *,
    similarity: NarrativeSimilarity | None = None,
    fraud_classifier: FraudClassifier | None = None,
    anomaly_detector: AnomalyDetector | None = None,
    workspace_id: UUID | None = None,
) -> AsyncIterator[ImportStreamEvent]:
    """Async-generator that processes claims one at a time, streaming events.

    Args:
        records:           Pre-parsed list of ClaimDetail objects.
        filename:          Original file name (for the ImportStartedEvent).
        session:           AsyncSession or None (dry-run mode when None).
        similarity:        NarrativeSimilarity port; skipped when None.
        fraud_classifier:  FraudClassifier port; skipped when None.
        anomaly_detector:  AnomalyDetector port; skipped when None.
        workspace_id:      User-scoped workspace; None for shared space.
    """
    return _generate(
        records=records,
        filename=filename,
        session=session,
        similarity=similarity,
        fraud_classifier=fraud_classifier,
        anomaly_detector=anomaly_detector,
        workspace_id=workspace_id,
    )


async def _generate(
    *,
    records: list[ClaimDetail],
    filename: str,
    session: AsyncSession | None,
    similarity: NarrativeSimilarity | None,
    fraud_classifier: FraudClassifier | None,
    anomaly_detector: AnomalyDetector | None,
    workspace_id: UUID | None,
) -> AsyncIterator[ImportStreamEvent]:  # type: ignore[misc]
    """The actual async-generator body."""
    yield ImportStartedEvent(
        data=ImportStartedData(total_rows=len(records), filename=filename)
    )

    imported = 0
    skipped = 0
    errors: list[str] = []
    # (claim_id, descripcion) pairs to index AFTER the batch commit — the
    # claim_narratives FK requires the siniestros row to exist first, and the
    # similarity adapter commits in its own session (can't see uncommitted rows).
    to_index: list[tuple[str, str]] = []

    for row_idx, claim in enumerate(records):
        # ── 1. ParseRow ───────────────────────────────────────────────────────
        yield ParseRowEvent(
            data=ParseRowData(
                row_index=row_idx,
                claim_id=claim.id,
                ramo=claim.ramo,
                cobertura=claim.cobertura,
            )
        )

        try:
            # ── 2. CaseStarted ────────────────────────────────────────────────
            yield CaseStartedEvent(
                data=CaseStartedData(claim_id=claim.id, row_index=row_idx)
            )

            # ── 3. Build enriched RuleContext ─────────────────────────────────
            ctx = await _build_enriched_context(claim, session)

            # ── 4-5. Narrative similarity enrichment (embed-on-the-fly) ───────
            # Query neighbours WITHOUT indexing this claim first — its siniestros
            # row isn't committed yet, so indexing now would violate the
            # claim_narratives FK. Indexing happens after the batch commit (below).
            if similarity is not None and claim.descripcion and len(claim.descripcion) >= 30:
                try:
                    similar_claims = await similarity.nearest_by_text(
                        claim.descripcion, top_k=3, exclude_claim_id=claim.id
                    )
                    top_sim = similar_claims[0].similarity if similar_claims else 0.0
                    ctx.narrativa_similar_score = top_sim
                    # narrativa_clonada drives RF-07 (≥0.98), NOT FS-13 (≥0.85)
                    from app.domain.rules.loader import rule_cfg as _rule_cfg

                    ctx.narrativa_clonada = top_sim >= _rule_cfg("RF_07")["threshold_similarity"]
                except Exception as exc:
                    logger.warning(
                        "stream_import: similarity.nearest failed for %s: %s", claim.id, exc
                    )
                    similar_claims = []
            else:
                similar_claims = []

            # ── 6. Evaluate all rules, streaming one event per rule ───────────
            rules = all_rules()
            meta_map = {r.META.code: r.META for r in rules}
            fired_count = 0

            for rule in rules:
                activation = rule.evaluate(claim, ctx)
                code = rule.META.code
                is_hard = code.startswith(_HARD_RULE_PREFIX)

                if activation is not None:
                    fired_count += 1
                    if is_hard:
                        yield RuleHardFiredEvent(
                            data=RuleHardFiredData(
                                claim_id=claim.id,
                                code=code,
                                tier_hint=activation.tier_hint.value,
                                evidence=activation.evidence,
                            )
                        )
                    else:
                        yield RuleScoringEvent(
                            data=RuleScoringData(
                                claim_id=claim.id,
                                code=code,
                                fired=True,
                                puntos=activation.points,
                                why_not=None,
                                evidence=activation.evidence,
                            )
                        )
                else:
                    if not is_hard:
                        # Emit a "skipped" scoring event so the UI lights it green
                        meta = meta_map.get(code)
                        yield RuleScoringEvent(
                            data=RuleScoringData(
                                claim_id=claim.id,
                                code=code,
                                fired=False,
                                puntos=0,
                                why_not=meta.what_triggers if meta else None,
                                evidence={},
                            )
                        )

            # ── 7. Aggregate score ────────────────────────────────────────────
            from app.domain.rules.aggregator import aggregate
            from app.schemas.risk import RuleActivation

            activations: list[RuleActivation] = []
            for rule in rules:
                result = rule.evaluate(claim, ctx)
                if result is not None:
                    activations.append(result)

            score, tier = aggregate(activations)

            # ── 8. ML score ───────────────────────────────────────────────────
            if fraud_classifier is not None:
                try:
                    features = extract_features(claim, ctx)
                    ml_pred = await fraud_classifier.predict(features)
                    yield MLScoredEvent(
                        data=MLScoredData(
                            claim_id=claim.id,
                            probability=ml_pred.probability,
                            top_factors=[f.feature for f in ml_pred.factors],
                        )
                    )
                except Exception as exc:
                    logger.warning("stream_import: ML score failed for %s: %s", claim.id, exc)

            # ── 9. Anomaly score ──────────────────────────────────────────────
            if anomaly_detector is not None:
                try:
                    features = extract_features(claim, ctx)
                    anomaly = await anomaly_detector.score(features)
                    yield AnomalyDetectedEvent(
                        data=AnomalyDetectedData(
                            claim_id=claim.id,
                            anomaly_score=anomaly.score,
                            nearest_normal_claim_id=anomaly.nearest_normal_claim_id,
                        )
                    )
                except Exception as exc:
                    logger.warning("stream_import: anomaly score failed for %s: %s", claim.id, exc)

            # ── 10. Similarity found event ────────────────────────────────────
            # The neighbours that clear the display floor are both streamed live
            # AND persisted (step 11) so the "Narrativas similares" panel renders
            # the real engine output instead of an empty list.
            display_similar = [
                s for s in similar_claims if s.similarity >= settings.SIMILARITY_DISPLAY_MIN
            ][:3]
            if display_similar:
                yield SimilarityFoundEvent(
                    data=SimilarityFoundData(
                        claim_id=claim.id,
                        matches=[
                            SimilarClaimRef(
                                claim_id=s.claim_id,
                                similarity=s.similarity,
                                snippet=s.snippet,
                            )
                            for s in display_similar
                        ],
                    )
                )

            # ── 11. Persist ───────────────────────────────────────────────────
            persisted = False
            if session is not None:
                try:
                    _sev = {"rojo": "high", "amarillo": "med", "verde": "low"}
                    alertas = [
                        ClaimAlert(
                            code=a.code,
                            puntos=a.points,
                            severidad=_sev.get(a.tier_hint.value, "low"),
                            detalle=(
                                m.short_description if (m := get_meta(a.code)) else a.code
                            ),
                            evidence=a.evidence,
                        )
                        for a in activations
                    ]
                    scored_claim = claim.model_copy(
                        update={
                            "score": score,
                            "nivel": tier,
                            "alertas": alertas,
                            "similar": [
                                SimilarClaim(
                                    claim_id=s.claim_id,
                                    similarity=s.similarity,
                                    snippet=s.snippet,
                                )
                                for s in display_similar
                            ],
                        }
                    )
                    async with session.begin_nested():
                        await _upsert_one(session, scored_claim, workspace_id=workspace_id)
                    persisted = True
                    imported += 1
                    # Index after the batch commit (FK target now guaranteed to exist).
                    if claim.descripcion and len(claim.descripcion) >= 30:
                        to_index.append((claim.id, claim.descripcion))
                except Exception as exc:
                    skipped += 1
                    msg = f"{claim.id}: persist failed: {exc}"
                    errors.append(msg)
                    logger.warning("stream_import: %s", msg)
                    yield ImportErrorEvent(
                        data=ImportErrorData(
                            row_index=row_idx,
                            claim_id=claim.id,
                            message=str(exc),
                        )
                    )
            else:
                # Dry-run mode: count as imported (score was computed, just not persisted)
                imported += 1

            # ── 12. CaseCompleted ─────────────────────────────────────────────
            yield CaseCompletedEvent(
                data=CaseCompletedData(
                    claim_id=claim.id,
                    score=score,
                    tier=tier.value,
                    persisted=persisted,
                    rules_fired=fired_count,
                )
            )

        except Exception as exc:
            skipped += 1
            msg = str(exc)
            errors.append(f"{claim.id}: {msg}")
            logger.warning("stream_import: row %d (%s) failed: %s", row_idx, claim.id, exc)
            yield ImportErrorEvent(
                data=ImportErrorData(
                    row_index=row_idx,
                    claim_id=claim.id,
                    message=msg,
                )
            )

    # ── Final commit + aggregates ─────────────────────────────────────────────
    if session is not None and imported > 0:
        try:
            await compute_aggregates(session)
            await session.commit()
        except Exception as exc:
            logger.error("stream_import: post-batch commit failed: %s", exc)

    # ── Index narratives now that the siniestros rows are committed ────────────
    # (claim_narratives FK → siniestros; must run after the commit above).
    if similarity is not None and to_index:
        try:
            await similarity.index_many(to_index)
        except Exception as exc:
            logger.warning("stream_import: similarity.index_many failed: %s", exc)

    yield ImportCompletedEvent(
        data=ImportCompletedData(imported=imported, skipped=skipped, errors=errors)
    )


# ---------------------------------------------------------------------------
# Context enrichment
# ---------------------------------------------------------------------------


async def _build_enriched_context(claim: ClaimDetail, session: AsyncSession | None) -> RuleContext:
    """Build a RuleContext from ClaimDetail, then enrich with DB lookups when available."""
    ctx = RuleContext.from_claim(claim)

    if session is None:
        return ctx  # dry-run: use only what can be derived from the claim itself

    # ── Provider restrictive-list check ──────────────────────────────────────
    if claim.proveedor:
        try:
            prov: Proveedor | None = await session.get(Proveedor, claim.proveedor)
            if prov is not None:
                ctx.proveedor_en_lista_restrictiva = prov.porcentaje_casos_observados >= 0.5
                ctx.proveedor_casos_observados = prov.reclamos_asociados
        except Exception as exc:
            logger.debug("stream_import: provider lookup failed for %s: %s", claim.proveedor, exc)

    # ── Historical frequency for insured ─────────────────────────────────────
    try:
        from datetime import UTC, datetime, timedelta

        cutoff = datetime.now(tz=UTC).date() - timedelta(days=548)  # ~18 months
        freq_stmt = (
            select(func.count())
            .select_from(Siniestro)
            .where(
                Siniestro.id_asegurado == claim.asegurado_id,
                Siniestro.fecha_ocurrencia >= cutoff,
            )
        )
        result = await session.execute(freq_stmt)
        ctx.historial_siniestros_asegurado = int(result.scalar() or 0)
    except Exception as exc:
        logger.debug("stream_import: insured frequency lookup failed: %s", exc)

    # ── Document inconsistency / falsification flags ──────────────────────────
    doc_texts = " ".join((d.tipo or "").lower() for d in claim.documentos)
    if any(m in doc_texts for m in _INCONSISTENCY_MARKERS):
        ctx.inconsistencia_documental = True
    if any(m in doc_texts for m in _FALSIFICATION_MARKERS):
        ctx.falsificacion_evidente = True

    return ctx


# ---------------------------------------------------------------------------
# Persistence (mirrors _use_case._upsert_one)
# ---------------------------------------------------------------------------


async def _upsert_one(
    session: AsyncSession,
    claim: ClaimDetail,
    *,
    workspace_id: UUID | None,
) -> None:
    """Upsert a scored claim into all relevant tables."""
    await session.merge(claim_detail_to_asegurado(claim))
    await session.flush()

    await session.merge(claim_detail_to_poliza(claim))
    await session.flush()

    proveedor = claim_detail_to_proveedor(claim)
    if proveedor is not None:
        await session.merge(proveedor)
        await session.flush()

    await session.merge(claim_detail_to_siniestro(claim, workspace_id=workspace_id))
    await session.flush()

    for doc in claim_detail_to_documentos(claim):
        await session.merge(doc)
    await session.flush()

    score_row = claim_detail_to_score_row(claim)
    await upsert_claim_score(session, score_row)
    await session.flush()
