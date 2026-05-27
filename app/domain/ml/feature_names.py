"""Canonical, ordered list of feature names produced by ``extract_features``.

Pinned here (rather than recomputed from a dict) so:
  - the LightGBM Booster, IsolationForest, and NearestNeighbors share the same
    column order at training and inference (drift here = silent bad predictions);
  - tests can assert the contract without running the extractor on a fixture;
  - the training notebook reads the canonical list and can compare its trained
    ``Booster.feature_name()`` against it to detect drift.

If you add or remove a feature in ``features.py``, update this list in the same
PR. The two are kept in lockstep on purpose.
"""

from __future__ import annotations

FEATURE_NAMES: tuple[str, ...] = (
    # ── numeric: temporal + amounts ────────────────────────────────────────────
    "monto_reclamado",
    "suma_asegurada",
    "monto_vs_suma_pct",
    "monto_vs_reparacion_avg_pct",
    "dias_entre_ocurrencia_reporte",
    "dias_desde_inicio_poliza",
    "dias_desde_fin_poliza",
    "demora_denuncia_horas",
    # ── numeric: frequency ────────────────────────────────────────────────────
    "historial_siniestros_asegurado",
    "frecuencia_vehiculo",
    "frecuencia_conductor",
    "eventos_rc_previos",
    "proveedor_casos_observados",
    # ── numeric: narrative ────────────────────────────────────────────────────
    "narrativa_similar_score",
    # ── boolean (0/1) ─────────────────────────────────────────────────────────
    "documentos_incompletos",
    "inconsistencia_documental",
    "narrativa_clonada",
    "evento_medianoche",
    "es_robo",
    "cobertura_rc",
    "proveedor_en_lista_restrictiva",
    "beneficiario_en_lista_restrictiva",
    "narrativa_ilogica",
    # ── deliberately EXCLUDED to avoid label leakage ─────────────────────────
    # The following RuleContext flags trip a hard RF-* rule and force tier=rojo
    # at generation time, which is also the source of ``etiqueta_fraude_simulada``.
    # Including them lets the model trivially memorize the rules engine. We keep
    # them out so the model has to learn from softer signals (frequency, timing,
    # amounts, narrative). See docs/uso_ia.md for the full rationale.
    #   es_cobertura_ptxrb       → RF-01
    #   falsificacion_evidente   → RF-02
    #   dinamica_imposible       → RF-04
    #   sin_rastro_tercero       → strong FS-10 contributor
)
"""Ordered canonical feature vector. Length 23."""
