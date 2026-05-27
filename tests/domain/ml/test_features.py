"""Feature extractor contract tests.

The extractor is the single source of truth for the training pipeline AND the
runtime adapters; if the keys drift, inference silently regresses. We pin the
contract here.
"""

from __future__ import annotations

from app.domain.ml import FEATURE_NAMES, extract_features
from app.domain.rules.context import RuleContext
from tests.fixtures.claims import claim_amarillo, claim_rojo, claim_verde


def test_feature_names_match_extractor_output() -> None:
    claim = claim_verde()
    ctx = RuleContext.from_claim(claim)
    features = extract_features(claim, ctx)
    assert set(features.keys()) == set(FEATURE_NAMES)


def test_features_are_floats() -> None:
    claim = claim_amarillo()
    ctx = RuleContext.from_claim(claim)
    features = extract_features(claim, ctx)
    for name, value in features.items():
        assert isinstance(value, float), f"feature {name!r} is {type(value).__name__}, not float"


def test_features_capture_amounts_and_dates() -> None:
    claim = claim_amarillo()
    ctx = RuleContext.from_claim(claim)
    features = extract_features(claim, ctx)

    assert features["monto_reclamado"] == claim.monto_reclamado
    assert features["suma_asegurada"] == claim.suma_asegurada
    # claim_amarillo: 2026-04-05 → 2026-04-14 = 9 días
    assert features["dias_entre_ocurrencia_reporte"] == 9.0


def test_boolean_features_become_zero_one() -> None:
    claim = claim_rojo()  # PTxRB coverage, doc faltante → flags set
    ctx = RuleContext.from_claim(claim)
    features = extract_features(claim, ctx)

    assert features["documentos_incompletos"] in (0.0, 1.0)
    assert features["es_robo"] in (0.0, 1.0)
    # rojo fixture is theft total loss
    assert features["es_robo"] == 1.0


def test_no_leakage_feature_in_canonical_list() -> None:
    """Leakage flags (hard-rule signals) must NOT appear in FEATURE_NAMES.

    See ``feature_names.py`` for the full anti-leakage rationale.
    """
    forbidden = {
        "es_cobertura_ptxrb",
        "falsificacion_evidente",
        "dinamica_imposible",
        "sin_rastro_tercero",
    }
    assert forbidden.isdisjoint(set(FEATURE_NAMES))
