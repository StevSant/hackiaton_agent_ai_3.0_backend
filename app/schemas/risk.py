"""Scoring-engine contract: the output of `score_claim` (rules + ml + anomaly + similarity).

This is what Track B (rules + ML) builds against. The wire/UI projection lives in
`schemas/claim.py`. Tier bands per challenge spec §2.1 (🟢 0-40 / 🟡 41-75 / 🔴 76-100).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class Tier(str, Enum):
    """Traffic-light triage tier. Matches the frontend `RiskTier` union."""

    verde = "verde"  # 0-40  → normal flow
    amarillo = "amarillo"  # 41-75 → Antifraud Unit, document review
    rojo = "rojo"  # 76-100 → Antifraud Unit, field review


class RuleActivation(BaseModel):
    """One fired fraud rule, produced by the rules engine (`domain/rules`).

    `points` is 0 for hard rules (RF-*) — they override via `tier_hint`.
    `evidence` carries the variables that made the rule fire; it is what the UI
    renders under "Reglas activadas" (be specific — numbers, not adjectives).
    """

    code: str = Field(..., examples=["FS-07", "RF-01"])
    points: int
    tier_hint: Tier
    evidence: dict[str, Any] = Field(default_factory=dict)  # heterogeneous, rule-specific JSON


class FactorContribution(BaseModel):
    """One SHAP contributor from the supervised model (top-3 surfaced)."""

    feature: str
    shap_value: float
    direction: Literal["up", "down"]


class SimilarClaim(BaseModel):
    """A narrative-similar prior claim (pgvector cosine)."""

    claim_id: str
    similarity: float = Field(..., ge=0.0, le=1.0)
    snippet: str


class ClaimRiskScore(BaseModel):
    """Full output of `score_claim`: rules + ml + anomaly + similarity.

    The ML probability is kept SEPARATE from the additive rules `score` so the
    analyst sees rules vs. model independently (explainability, §2.4).
    """

    score: int = Field(..., ge=0, le=100)
    tier: Tier
    activations: list[RuleActivation] = Field(default_factory=list)
    ml_probability: float | None = None
    ml_factors: list[FactorContribution] = Field(default_factory=list)
    anomaly_score: float | None = None
    nearest_normal_claim_id: str | None = None
    similar: list[SimilarClaim] = Field(default_factory=list)
    # A2 — signal-agreement flags. NEVER an accusation: a review prompt.
    posible_falso_positivo: bool = False
    confianza: Literal["alta", "media", "baja"] = "alta"
    computed_at: datetime
