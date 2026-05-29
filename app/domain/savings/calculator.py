"""Domain VO + pure calculator for "ahorro potencial" (potential savings) estimates.

Formula (single source of truth):
    exposicion           = max(0, min(monto_reclamado, suma_asegurada) - monto_pagado - deducible)
    prob_fraude          = ml_probability  if present  else  score / 100
    valor_en_riesgo      = exposicion
    ahorro_potencial_est = exposicion * prob_fraude * tasa_recuperacion

No I/O, no framework imports — pure domain logic.
"""

from __future__ import annotations

from pydantic import BaseModel


class SavingsEstimate(BaseModel):
    """Value object returned by estimate_savings."""

    exposicion: float
    valor_en_riesgo: float
    prob_fraude_usada: float
    ahorro_potencial_estimado: float


def estimate_savings(
    *,
    monto_reclamado: float,
    suma_asegurada: float,
    monto_pagado: float = 0.0,
    deducible: float = 0.0,
    score: int,
    ml_probability: float | None = None,
    tasa_recuperacion: float,
) -> SavingsEstimate:
    """Compute the potential savings estimate for a single claim.

    Args:
        monto_reclamado: Amount claimed by the insured.
        suma_asegurada:  Policy coverage cap.
        monto_pagado:    Amount already paid by the insurer (defaults 0).
        deducible:       Policy deductible (defaults 0).
        score:           Rules-engine risk score 0-100.
        ml_probability:  ML fraud probability [0,1]; overrides score when present.
        tasa_recuperacion: Recovery rate from settings.TASA_RECUPERACION_AHORRO.

    Returns:
        SavingsEstimate with all monetary outputs rounded to 2 decimals.
    """
    exposicion = max(0.0, min(monto_reclamado, suma_asegurada) - monto_pagado - deducible)
    prob_fraude = ml_probability if ml_probability is not None else score / 100.0
    ahorro = exposicion * prob_fraude * tasa_recuperacion

    return SavingsEstimate(
        exposicion=round(exposicion, 2),
        valor_en_riesgo=round(exposicion, 2),
        prob_fraude_usada=round(prob_fraude, 4),
        ahorro_potencial_estimado=round(ahorro, 2),
    )
