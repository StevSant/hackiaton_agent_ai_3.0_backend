"""Tier mapper: additive score → triage tier.

Bands per challenge spec §2.1:
  verde    0-40
  amarillo 41-75
  rojo     76-100
"""

from __future__ import annotations

from app.domain.rules.loader import tier_bands
from app.schemas.risk import Tier


def score_to_tier(score: int) -> Tier:
    """Map an additive score [0, 100] to a Tier.

    Uses thresholds from config.yaml so they can be tuned without touching code.
    """
    bands = tier_bands()
    verde_max: int = bands["verde_max"]
    amarillo_max: int = bands["amarillo_max"]

    if score <= verde_max:
        return Tier.verde
    if score <= amarillo_max:
        return Tier.amarillo
    return Tier.rojo
