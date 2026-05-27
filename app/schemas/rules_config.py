"""Wire schema for GET /rules/config — extended catalog with runtime state.

Extends the bare RuleMetaOut from schemas/rules.py with:
- kind: how the rule contributes (critical override, yellow override, additive score)
- activaciones_30d: count of times the rule fired in the last 30 days
- enabled: whether the rule is active in the engine
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

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
