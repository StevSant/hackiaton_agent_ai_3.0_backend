"""Map fired-rule codes → the signal *facts* that imply them.

Used to back-fill ``siniestros.signals`` from a claim's existing (curated)
activations so the rules engine can reproduce the same scenario from facts
instead of hand-authored scores. Both code schemes are covered:

- The demo / curated scheme (``RF01``, ``AF01`` …) used by ``demo_claims.json``.
- The canonical engine scheme (``RF-01``, ``FS-03`` …) emitted by ``score_claim``.

Codes that map to ``{}`` are fully derivable from the claim's own data (dates,
amounts, coverage, document completeness) and therefore need no stored fact —
``build_rule_context_from_db`` re-derives them.
"""

from __future__ import annotations

from typing import Any

ACTIVATION_CODE_TO_SIGNALS: dict[str, dict[str, Any]] = {
    # ── Hard rules (RF) ──────────────────────────────────────────────────────
    "RF01": {},  # coverage-derived from cobertura
    "RF-01": {},
    "RF02": {"falsificacion_evidente": True},
    "RF-02": {"falsificacion_evidente": True},
    "RF03": {"beneficiario_en_lista_restrictiva": True},
    "RF-03": {"beneficiario_en_lista_restrictiva": True},
    "RF04": {"dinamica_imposible": True},
    "RF-04": {"dinamica_imposible": True},
    "RF05": {},  # date-derived
    "RF-05": {},
    "RF06": {},  # date-derived
    "RF-06": {},
    "RF07": {"narrativa_clonada": True, "narrativa_similar_score": 0.99},
    "RF-07": {"narrativa_clonada": True, "narrativa_similar_score": 0.99},
    # ── Scored signals (FS / AF) ─────────────────────────────────────────────
    "AF01": {"historial_siniestros_asegurado": 3},
    "FS-03": {"historial_siniestros_asegurado": 3},
    "FS-04": {"frecuencia_vehiculo": 3},
    "FS-05": {"frecuencia_conductor": 3},
    "FS-06": {"eventos_rc_previos": 3},
    "AF02": {},  # doc-derived
    "FS-08": {},
    "FS-09": {"narrativa_ilogica": True},
    "AF05": {"sin_rastro_tercero": True},
    "FS-10": {"sin_rastro_tercero": True},
    "FS-11": {"inconsistencia_documental": True},
    "AF03": {},  # date-derived
    "FS-12": {},
    "AF04": {},  # amount-derived
    "FS-14": {},
    "FS-13": {"narrativa_similar_score": 0.9, "narrativa_clonada": False},
}


def signals_from_activations(activations: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge the per-code signal facts implied by a claim's activations.

    Each activation dict carries a ``"code"`` key. Unknown codes contribute
    nothing. When two activations imply the same key, the later one wins (e.g.
    RF-07's ``narrativa_clonada=True`` overrides FS-13's ``False``), which is the
    correct precedence since a cloned narrative subsumes a merely-similar one.
    """
    merged: dict[str, Any] = {}
    for activation in activations:
        code = activation.get("code")
        if not code:
            continue
        merged.update(ACTIVATION_CODE_TO_SIGNALS.get(code, {}))
    return merged
