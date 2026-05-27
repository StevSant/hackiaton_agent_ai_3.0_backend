"""Feature engineering: ``ClaimDetail`` + ``RuleContext`` → flat ``dict[str, float]``.

Single source of truth for both training (notebook 02) and inference
(``enrich_claim_score`` via the LightGBM / IsolationForest adapters).

The output dict's keys MUST match ``FEATURE_NAMES`` verbatim (order doesn't
matter at the dict level — the adapters re-order per ``Booster.feature_name()``
at inference time). Adding a feature is a 2-line PR: extend ``FEATURE_NAMES``
and emit it here.

WHY no leakage features: see the note at the bottom of ``feature_names.py``.
"""

from __future__ import annotations

from app.domain.ml.feature_names import FEATURE_NAMES
from app.domain.rules.context import RuleContext
from app.schemas.claim import ClaimDetail


def _b(value: bool) -> float:
    """Bool → 0.0 / 1.0 (LightGBM and IsolationForest both want numeric)."""
    return 1.0 if value else 0.0


def extract_features(claim: ClaimDetail, ctx: RuleContext) -> dict[str, float]:
    """Build the canonical feature vector for *claim* given its rule context.

    Args:
        claim: Full claim detail (carries amounts + raw dates).
        ctx:   Derived rule context (carries the frequency, document, and
               narrative signals that aren't on the raw claim).

    Returns:
        A dict keyed by every name in ``FEATURE_NAMES``. Missing values are 0.0;
        the adapters cope with that via their own ``features.get(name, 0.0)``
        fallback, but we materialize the full dict here so tests can assert the
        contract.
    """
    features: dict[str, float] = {
        # numeric: temporal + amounts
        "monto_reclamado": float(claim.monto_reclamado),
        "suma_asegurada": float(claim.suma_asegurada),
        "monto_vs_suma_pct": float(ctx.monto_vs_suma_pct),
        "monto_vs_reparacion_avg_pct": float(ctx.monto_vs_reparacion_avg_pct),
        "dias_entre_ocurrencia_reporte": float(ctx.dias_entre_ocurrencia_reporte),
        "dias_desde_inicio_poliza": float(ctx.dias_desde_inicio_poliza),
        "dias_desde_fin_poliza": float(ctx.dias_desde_fin_poliza),
        "demora_denuncia_horas": float(ctx.demora_denuncia_horas),
        # numeric: frequency
        "historial_siniestros_asegurado": float(ctx.historial_siniestros_asegurado),
        "frecuencia_vehiculo": float(ctx.frecuencia_vehiculo),
        "frecuencia_conductor": float(ctx.frecuencia_conductor),
        "eventos_rc_previos": float(ctx.eventos_rc_previos),
        "proveedor_casos_observados": float(ctx.proveedor_casos_observados),
        # numeric: narrative
        "narrativa_similar_score": float(ctx.narrativa_similar_score),
        # boolean → 0/1
        "documentos_incompletos": _b(ctx.documentos_incompletos),
        "inconsistencia_documental": _b(ctx.inconsistencia_documental),
        "narrativa_clonada": _b(ctx.narrativa_clonada),
        "evento_medianoche": _b(ctx.evento_medianoche),
        "es_robo": _b(ctx.es_robo),
        "cobertura_rc": _b(ctx.cobertura_rc),
        "proveedor_en_lista_restrictiva": _b(ctx.proveedor_en_lista_restrictiva),
        "beneficiario_en_lista_restrictiva": _b(ctx.beneficiario_en_lista_restrictiva),
        "narrativa_ilogica": _b(ctx.narrativa_ilógica),
    }

    # Contract check — if extract_features and FEATURE_NAMES drift, fail loudly.
    missing = set(FEATURE_NAMES) - features.keys()
    extra = features.keys() - set(FEATURE_NAMES)
    if missing or extra:
        raise RuntimeError(
            "extract_features keys drift vs FEATURE_NAMES — "
            f"missing={sorted(missing)} extra={sorted(extra)}"
        )

    return features
