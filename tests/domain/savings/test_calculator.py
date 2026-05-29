"""TDD tests for app.domain.savings.calculator.

Formula:
    exposicion           = max(0, min(monto_reclamado, suma_asegurada) - monto_pagado - deducible)
    prob_fraude          = ml_probability if present else score / 100
    ahorro_potencial_est = exposicion * prob_fraude * tasa_recuperacion
"""

from __future__ import annotations

import pytest

from app.domain.savings.calculator import SavingsEstimate, estimate_savings

TASA = 0.6  # canonical default


def _estimate(**kwargs: object) -> SavingsEstimate:
    defaults = dict(
        monto_reclamado=10_000.0,
        suma_asegurada=20_000.0,
        monto_pagado=0.0,
        deducible=0.0,
        score=50,
        ml_probability=None,
        tasa_recuperacion=TASA,
    )
    defaults.update(kwargs)
    return estimate_savings(**defaults)  # type: ignore[arg-type]


def test_normal_claim() -> None:
    """Standard case: full claim with 50% score and no prior payment."""
    result = _estimate(
        monto_reclamado=10_000.0,
        suma_asegurada=20_000.0,
        monto_pagado=0.0,
        deducible=0.0,
        score=50,
    )
    # exposicion = min(10000, 20000) - 0 - 0 = 10000
    assert result.exposicion == 10_000.0
    # prob = 50/100 = 0.50
    assert result.prob_fraude_usada == 0.5
    # ahorro = 10000 * 0.50 * 0.6 = 3000
    assert result.ahorro_potencial_estimado == 3_000.0
    assert result.valor_en_riesgo == 10_000.0


def test_exposure_floored_at_zero_when_already_paid_plus_deductible_exceeds_claim() -> None:
    """When paid + deductible >= claimed, exposure is 0 → ahorro is 0."""
    result = _estimate(
        monto_reclamado=5_000.0,
        suma_asegurada=20_000.0,
        monto_pagado=4_500.0,
        deducible=1_000.0,
        score=80,
    )
    # min(5000, 20000) - 4500 - 1000 = -500 → max(0, -500) = 0
    assert result.exposicion == 0.0
    assert result.ahorro_potencial_estimado == 0.0


def test_exposure_capped_by_suma_asegurada_when_claimed_exceeds_it() -> None:
    """Claimed > suma_asegurada: exposure limited to suma_asegurada."""
    result = _estimate(
        monto_reclamado=30_000.0,
        suma_asegurada=20_000.0,
        monto_pagado=0.0,
        deducible=0.0,
        score=70,
    )
    # min(30000, 20000) = 20000 → exposicion = 20000
    assert result.exposicion == 20_000.0
    # prob = 70/100 = 0.70
    assert result.prob_fraude_usada == 0.7
    # ahorro = 20000 * 0.70 * 0.6 = 8400
    assert result.ahorro_potencial_estimado == pytest.approx(8_400.0, abs=0.01)


def test_already_paid_claim_produces_near_zero_ahorro() -> None:
    """monto_pagado == monto_reclamado → exposure 0 → ahorro 0."""
    result = _estimate(
        monto_reclamado=8_000.0,
        suma_asegurada=15_000.0,
        monto_pagado=8_000.0,
        deducible=0.0,
        score=90,
    )
    assert result.exposicion == 0.0
    assert result.ahorro_potencial_estimado == 0.0


def test_ml_probability_none_falls_back_to_score() -> None:
    """When ml_probability is None, prob_fraude = score / 100."""
    result = _estimate(score=40, ml_probability=None)
    assert result.prob_fraude_usada == pytest.approx(0.4, abs=1e-4)


def test_ml_probability_present_overrides_score() -> None:
    """When ml_probability is provided, it overrides score/100."""
    result = _estimate(score=10, ml_probability=0.85)
    assert result.prob_fraude_usada == pytest.approx(0.85, abs=1e-4)
    # ahorro = exposicion * 0.85 * 0.6
    expected_ahorro = result.exposicion * 0.85 * TASA
    assert result.ahorro_potencial_estimado == pytest.approx(expected_ahorro, abs=0.01)


def test_output_is_rounded_to_two_decimals() -> None:
    """Monetary outputs must be rounded to 2 decimal places."""
    result = _estimate(
        monto_reclamado=10_001.0,
        suma_asegurada=20_000.0,
        monto_pagado=0.0,
        deducible=0.0,
        score=33,
    )
    # exposicion = 10001
    # prob = 0.33
    # ahorro = 10001 * 0.33 * 0.6 = 1980.198
    assert result.ahorro_potencial_estimado == round(10_001.0 * 0.33 * TASA, 2)
    assert result.exposicion == round(10_001.0, 2)
