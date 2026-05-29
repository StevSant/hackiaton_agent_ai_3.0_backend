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
    await _enrich_rc_events(session, claim, ctx)
    _enrich_document_markers(claim, ctx)
    await _enrich_similarity(claim, ctx, similarity)
    await _enrich_vehicle_identity(claim, ctx, decoder)
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
            # Restrictive-list membership (RF-03, hard rojo) is a curated blocklist
            # FACT, not a function of the observed-case ratio. Deriving it from
            # porcentaje_casos_observados made RF-03 fire for ~half the portfolio.
            # It now comes ONLY from the stored `signals` overlay (the genuinely
            # list-matched claims). The observed-case COUNT still feeds FS-07's
            # recurrent-provider path below.
            ctx.proveedor_casos_observados = prov.reclamos_asociados
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
    session: AsyncSession, claim: ClaimDetail, ctx: RuleContext
) -> None:
    """COUNT of prior RC-only claims for the insured (cobertura ~ 'Responsabilidad Civil')."""
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
) -> None:
    """Narrative similarity via the port: top-1 score + RF-07 cloned flag.

    Also stashes the display-worthy neighbours (>= SIMILARITY_DISPLAY_MIN) in
    ``ctx.extra["similar_claims"]`` so ``rescore_one`` can persist them into
    ``claim_scores.similar`` — that JSONB column is what feeds the
    "Narrativas similares" panel. Without this the computed matches would be
    discarded and the panel would always read empty.
    """
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
