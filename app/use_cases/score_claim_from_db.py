"""build_rule_context_from_db — assemble a RuleContext from DB relationships.

This is the single source of truth for *how a claim's risk context is built
from the database* so ``score_claim`` produces a genuine, reproducible score:

1. Start from ``RuleContext.from_claim`` (dates, coverage, amount, doc
   completeness, theft flags, denouncement delay — all derived from the claim).
2. Enrich with relationship-derived signals that need DB round-trips:
   provider restrictive/observed counts, insured 18-month claim frequency,
   document inconsistency / falsification markers, vehicle frequency
   (shared placa/chasis), and prior RC-only events for the insured.
3. Add narrative similarity via the ``NarrativeSimilarity`` port when provided.
4. Overlay the stored ``siniestros.signals`` JSONB. These are the investigator /
   NLP-provided ground-truth facts that *cannot* be derived from relationships;
   when a key is present it WINS over the derived value.

Mirrors the enrichment in ``import_claims_stream._build_enriched_context`` and
extends it with the vehicle / RC-event frequency lookups.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.rules.context import RuleContext
from app.domain.rules.loader import rule_cfg
from app.domain.similarity import NarrativeSimilarity
from app.domain.vehicle_identity import (
    VehicleDecoder,
    VehicleSpec,
    compare_vehicle,
)
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.claim import ClaimDetail

logger = logging.getLogger(__name__)

# Markers in document text that indicate inconsistency / falsification.
_INCONSISTENCY_MARKERS = frozenset(
    ["adulterada", "alterada", "falsificada", "falsa", "inconsist"]
)
_FALSIFICATION_MARKERS = frozenset(["falsificada", "falsa", "adulterada"])

# 18 months ≈ 548 days (matches the import-stream insured-frequency window).
_FREQUENCY_WINDOW_DAYS = 548

# Numeric keys that overlay integer context fields when present in signals.
_INT_SIGNAL_KEYS = (
    "historial_siniestros_asegurado",
    "frecuencia_vehiculo",
    "frecuencia_conductor",
    "eventos_rc_previos",
    "proveedor_casos_observados",
)
# Boolean keys that overlay boolean context fields when present in signals.
_BOOL_SIGNAL_KEYS = (
    "dinamica_imposible",
    "sin_rastro_tercero",
    "evento_medianoche",
    "falsificacion_evidente",
    "inconsistencia_documental",
    "narrativa_clonada",
    "proveedor_en_lista_restrictiva",
    "beneficiario_en_lista_restrictiva",
)


async def build_rule_context_from_db(
    session: AsyncSession,
    claim: ClaimDetail,
    *,
    similarity: NarrativeSimilarity | None = None,
    decoder: VehicleDecoder | None = None,
) -> RuleContext:
    """Build a fully-enriched RuleContext for *claim* from the database.

    Args:
        session:    AsyncSession used for the relationship lookups.
        claim:      Hydrated ClaimDetail (gives the derivable context base).
        similarity: NarrativeSimilarity port; narrative signals skipped when None.
        decoder:    VehicleDecoder port; FS-15 vehicle-identity check skipped
                    when None (back-compatible — older callers pass nothing).

    Returns:
        A RuleContext ready to feed ``score_claim(claim, ctx=ctx)``.
    """
    ctx = RuleContext.from_claim(claim)
    sin: Siniestro | None = await session.get(Siniestro, claim.id)

    await _enrich_provider(session, sin, claim, ctx)
    await _enrich_insured_frequency(session, claim, ctx)
    await _enrich_vehicle_frequency(session, claim, ctx)
    # Pass sin so the RC enricher can use asegurado.reclamos_rc_sin_tercero when present.
    await _enrich_rc_events(session, claim, ctx, sin=sin)
    _enrich_document_markers(claim, ctx)
    # Pass sin so similarity can use siniestro.similitud_narrativa_max when present.
    await _enrich_similarity(claim, ctx, similarity, sin=sin)
    await _enrich_vehicle_identity(claim, ctx, decoder)
    # FS-16: police report presence (only meaningful for theft claims)
    _enrich_police_report(sin, ctx)
    # FS-18: provider concentration (pair count) — needs session
    await _enrich_provider_concentration(session, sin, claim, ctx)
    # FS-19: insured risk profile
    await _enrich_insured_profile(session, sin, ctx)
    # FS-14 repair branch: over-estimation ratio vs monto_estimado
    _enrich_repair_ratio(sin, claim, ctx)
    _overlay_stored_signals(sin, ctx)

    return ctx


# ---------------------------------------------------------------------------
# Relationship-derived enrichment
# ---------------------------------------------------------------------------


async def _enrich_provider(
    session: AsyncSession,
    sin: Siniestro | None,
    claim: ClaimDetail,
    ctx: RuleContext,
) -> None:
    """Restrictive-list + observed-case counts from the Proveedor row.

    The provider primary key is the persisted ``siniestros.beneficiario`` slug;
    the display name on ``claim.proveedor`` is not the key. When the claim is not
    yet persisted (``sin is None``) there is no provider key to look up, so the
    enrichment is skipped (the caller's own provider logic, if any, applies).
    """
    provider_id = sin.beneficiario if sin is not None else None
    if not provider_id:
        return
    try:
        prov: Proveedor | None = await session.get(Proveedor, provider_id)
        if prov is not None:
            ctx.proveedor_casos_observados = prov.reclamos_asociados
            # Prefer the dataset ground-truth; fall back to the heuristic so
            # existing demo rows (without en_lista_restrictiva) are unchanged.
            ctx.proveedor_en_lista_restrictiva = (
                prov.en_lista_restrictiva
                if prov.en_lista_restrictiva is not None
                else (prov.porcentaje_casos_observados >= 0.5)
            )
    except Exception as exc:
        logger.debug("score_from_db: provider lookup failed for %s: %s", provider_id, exc)


async def _enrich_insured_frequency(
    session: AsyncSession, claim: ClaimDetail, ctx: RuleContext
) -> None:
    """COUNT of the insured's claims in the trailing 18 months."""
    try:
        cutoff = datetime.now(tz=UTC).date() - timedelta(days=_FREQUENCY_WINDOW_DAYS)
        stmt = (
            select(func.count())
            .select_from(Siniestro)
            .where(
                Siniestro.id_asegurado == claim.asegurado_id,
                Siniestro.id_siniestro != claim.id,
                Siniestro.fecha_ocurrencia >= cutoff,
            )
        )
        result = await session.execute(stmt)
        ctx.historial_siniestros_asegurado = int(result.scalar() or 0)
    except Exception as exc:
        logger.debug("score_from_db: insured frequency lookup failed: %s", exc)


async def _enrich_vehicle_frequency(
    session: AsyncSession, claim: ClaimDetail, ctx: RuleContext
) -> None:
    """COUNT of prior claims sharing the same placa or chasis (excluding self)."""
    vehiculo = claim.vehiculo
    placa = vehiculo.placa if vehiculo else None
    chasis = vehiculo.chasis if vehiculo else None
    if not placa and not chasis:
        return
    try:
        # Build the placa/chasis OR only over the columns we actually have.
        matchers = []
        if placa:
            matchers.append(Siniestro.placa == placa)
        if chasis:
            matchers.append(Siniestro.chasis == chasis)
        stmt = (
            select(func.count())
            .select_from(Siniestro)
            .where(
                or_(*matchers),
                Siniestro.id_siniestro != claim.id,
                Siniestro.fecha_ocurrencia < claim.fecha_ocurrencia,
            )
        )
        result = await session.execute(stmt)
        ctx.frecuencia_vehiculo = int(result.scalar() or 0)
    except Exception as exc:
        logger.debug("score_from_db: vehicle frequency lookup failed: %s", exc)


async def _enrich_rc_events(
    session: AsyncSession, claim: ClaimDetail, ctx: RuleContext, sin: Siniestro | None = None
) -> None:
    """RC-only event count for the insured.

    Prefers ``asegurado.reclamos_rc_sin_tercero`` from the dataset when not None
    (ground truth), then falls back to a COUNT of prior RC cobertura rows so
    existing demo data without the new field is unchanged.
    """
    # Ground-truth fast path: avoid the DB count when we have the precomputed value.
    if sin is not None:
        from app.infrastructure.db.models.asegurado import Asegurado as AseguradoModel
        try:
            aseg = await session.get(AseguradoModel, sin.id_asegurado)
            if aseg is not None and aseg.reclamos_rc_sin_tercero is not None:
                ctx.eventos_rc_previos = aseg.reclamos_rc_sin_tercero
                return
        except Exception as exc:
            logger.debug("score_from_db: asegurado RC lookup failed: %s", exc)

    # Fallback: count from the siniestros table (existing behaviour).
    try:
        stmt = (
            select(func.count())
            .select_from(Siniestro)
            .where(
                Siniestro.id_asegurado == claim.asegurado_id,
                Siniestro.id_siniestro != claim.id,
                Siniestro.fecha_ocurrencia < claim.fecha_ocurrencia,
                func.lower(Siniestro.cobertura).like("%responsabilidad civil%"),
            )
        )
        result = await session.execute(stmt)
        ctx.eventos_rc_previos = int(result.scalar() or 0)
    except Exception as exc:
        logger.debug("score_from_db: RC-events lookup failed: %s", exc)


def _enrich_document_markers(claim: ClaimDetail, ctx: RuleContext) -> None:
    """Document inconsistency / falsification flags from the document type text."""
    doc_texts = " ".join((d.tipo or "").lower() for d in claim.documentos)
    if any(m in doc_texts for m in _INCONSISTENCY_MARKERS):
        ctx.inconsistencia_documental = True
    if any(m in doc_texts for m in _FALSIFICATION_MARKERS):
        ctx.falsificacion_evidente = True


async def _enrich_similarity(
    claim: ClaimDetail,
    ctx: RuleContext,
    similarity: NarrativeSimilarity | None,
    sin: Siniestro | None = None,
) -> None:
    """Narrative similarity: top-1 score + RF-07 cloned flag.

    Prefers ``siniestros.similitud_narrativa_max`` (precomputed ground truth from
    the dataset) when not None; falls back to a live pgvector lookup so existing
    rows without the new field and the full "Narrativas similares" panel data are
    unaffected. The pgvector path is the only source of the neighbour list used
    by the panel — the precomputed field is a scalar only.
    """
    # Ground-truth fast path — skip pgvector when the dataset value is present.
    if sin is not None and sin.similitud_narrativa_max is not None:
        top_sim = sin.similitud_narrativa_max
        ctx.narrativa_similar_score = top_sim
        ctx.narrativa_clonada = top_sim >= rule_cfg("RF_07")["threshold_similarity"]
        # No neighbour list available from the precomputed scalar; panel stays empty
        # unless the pgvector corpus has been built (first-time run after ingest).
        return

    # Fallback: live pgvector nearest-neighbour lookup (existing behaviour).
    if similarity is None or not claim.descripcion or len(claim.descripcion) < 30:
        return
    try:
        nearest = await similarity.nearest(claim.id, top_k=3)
        top_sim = nearest[0].similarity if nearest else 0.0
        ctx.narrativa_similar_score = top_sim
        # narrativa_clonada drives RF-07 (≥ threshold), NOT FS-13 (≥ 0.85).
        ctx.narrativa_clonada = top_sim >= rule_cfg("RF_07")["threshold_similarity"]
        ctx.extra["similar_claims"] = [
            s for s in nearest if s.similarity >= settings.SIMILARITY_DISPLAY_MIN
        ]
    except Exception as exc:
        logger.warning("score_from_db: similarity.nearest failed for %s: %s", claim.id, exc)


async def _enrich_vehicle_identity(
    claim: ClaimDetail,
    ctx: RuleContext,
    decoder: VehicleDecoder | None,
) -> None:
    """FS-15: decode the chassis/VIN and flag when it contradicts the declared vehicle.

    Decodes the claim's chassis via the port, projects the declared vehicle into a
    ``VehicleSpec``, and compares. Any failure is swallowed (logged) so a decode
    error / registry outage never breaks scoring — the signal just stays off.
    """
    vehiculo = claim.vehiculo
    if decoder is None or vehiculo is None or not vehiculo.chasis:
        return
    try:
        decoded = await decoder.decode(vehiculo.chasis)
        declarado = VehicleSpec(
            marca=vehiculo.marca,
            modelo=vehiculo.modelo,
            anio=vehiculo.anio,
        )
        match = compare_vehicle(declarado, decoded, fuente="decoder")
        ctx.vehiculo_inconsistente = match.inconsistente
        ctx.vehiculo_campos_discrepantes = match.campos_discrepantes
    except Exception as exc:
        logger.warning(
            "score_from_db: vehicle-identity decode failed for %s: %s", claim.id, exc
        )


# ---------------------------------------------------------------------------
# Stored-signals overlay (ground truth wins)
# ---------------------------------------------------------------------------


def _enrich_police_report(sin: Siniestro | None, ctx: RuleContext) -> None:
    """FS-16: set tiene_parte_policial from the persisted numero_parte_policial column."""
    if sin is None:
        return
    # truthy non-empty string → has a police report number → safe default True
    ctx.tiene_parte_policial = bool(sin.numero_parte_policial and sin.numero_parte_policial.strip())


async def _enrich_provider_concentration(
    session: AsyncSession,
    sin: Siniestro | None,
    claim: ClaimDetail,
    ctx: RuleContext,
) -> None:
    """FS-18: provider total volume + provider+insured pair count.

    proveedor_total_siniestros: lifted from prov.reclamos_asociados (already fetched).
    pareja_proveedor_asegurado: COUNT of siniestros sharing the same beneficiario (provider)
    AND id_asegurado, excluding the current claim.
    """
    provider_id = sin.beneficiario if sin is not None else None
    if not provider_id:
        return
    try:
        prov: Proveedor | None = await session.get(Proveedor, provider_id)
        if prov is not None:
            ctx.proveedor_total_siniestros = prov.reclamos_asociados

        # Count the pareja (same provider + same insured, excluding self)
        stmt = (
            select(func.count())
            .select_from(Siniestro)
            .where(
                Siniestro.beneficiario == provider_id,
                Siniestro.id_asegurado == claim.asegurado_id,
                Siniestro.id_siniestro != claim.id,
            )
        )
        result = await session.execute(stmt)
        ctx.pareja_proveedor_asegurado = int(result.scalar() or 0)
    except Exception as exc:
        logger.debug("score_from_db: provider concentration lookup failed: %s", exc)


async def _enrich_insured_profile(
    session: AsyncSession,
    sin: Siniestro | None,
    ctx: RuleContext,
) -> None:
    """FS-19: populate perfil_riesgo from the asegurado row."""
    if sin is None:
        return
    try:
        from app.infrastructure.db.models.asegurado import Asegurado as AseguradoModel

        aseg = await session.get(AseguradoModel, sin.id_asegurado)
        if aseg is not None and aseg.perfil_riesgo:
            ctx.perfil_riesgo = aseg.perfil_riesgo
    except Exception as exc:
        logger.debug("score_from_db: insured profile lookup failed: %s", exc)


def _enrich_repair_ratio(
    sin: Siniestro | None, claim: ClaimDetail, ctx: RuleContext
) -> None:
    """FS-14 repair branch: monto_reclamado / monto_estimado when monto_estimado > 0.

    monto_estimado is the adjuster's estimate of actual repair cost (not the insured
    sum). A ratio > 1.5 means the claimant is requesting >150% of what repairs cost.
    """
    monto_estimado = sin.monto_estimado if sin is not None else None
    if monto_estimado and monto_estimado > 0:
        ctx.monto_vs_reparacion_avg_pct = claim.monto_reclamado / monto_estimado


def _overlay_stored_signals(sin: Siniestro | None, ctx: RuleContext) -> None:
    """Overlay the persisted ``siniestros.signals`` facts onto the context.

    Stored facts are the investigator / NLP ground truth that can't be derived
    from relationships, so any key present here overrides the derived value.
    ``narrativa_ilogica`` maps onto the accented context attribute.
    """
    signals: dict = dict(sin.signals or {}) if sin is not None else {}
    if not signals:
        return

    for key in _INT_SIGNAL_KEYS:
        if key in signals and signals[key] is not None:
            setattr(ctx, key, int(signals[key]))
    for key in _BOOL_SIGNAL_KEYS:
        if key in signals and signals[key] is not None:
            setattr(ctx, key, bool(signals[key]))

    if "narrativa_similar_score" in signals and signals["narrativa_similar_score"] is not None:
        ctx.narrativa_similar_score = float(signals["narrativa_similar_score"])
    # ASCII key in storage maps onto the accented context attribute.
    if "narrativa_ilogica" in signals and signals["narrativa_ilogica"] is not None:
        ctx.narrativa_ilógica = bool(signals["narrativa_ilogica"])
