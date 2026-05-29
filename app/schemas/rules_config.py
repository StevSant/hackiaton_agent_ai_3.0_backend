"""Wire schema for GET /rules/config + PATCH /rules/{code}.

Extends the bare RuleMetaOut from schemas/rules.py with:
- kind: how the rule contributes (critical override, yellow override, additive score)
- activaciones_30d: count of times the rule fired in the last 30 days
- enabled: whether the rule is active in the engine
- thresholds: the rule's effective numeric thresholds (config.yaml defaults with
  any persisted override merged in) — editable from the dashboard.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.risk import Tier


class RuleKind(str, Enum):
    critica = "critica"
    amarilla = "amarilla"
    scored = "scored"


class RuleConfigOut(BaseModel):
    code: str
    titulo: str
    descripcion: str
    clasificacion: Tier
    kind: RuleKind
    max_pts: int
    activaciones_30d: int
    enabled: bool
    # Effective numeric thresholds (e.g. {"tier1_days": 10}); empty for rules with
    # no tunable thresholds. Powers the dashboard threshold editor.
    thresholds: dict[str, float] = Field(default_factory=dict)


class RuleConfigPatch(BaseModel):
    """Body of PATCH /rules/{code} — at least one field must be provided.

    ``enabled`` pauses / reactivates the rule. ``thresholds`` is a partial overlay
    on the rule's config block; only known numeric keys are accepted (the use case
    rejects unknown keys and non-numeric values).
    """

    enabled: bool | None = None
    thresholds: dict[str, float] | None = None
