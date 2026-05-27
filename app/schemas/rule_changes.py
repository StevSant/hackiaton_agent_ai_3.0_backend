"""Wire schema for GET /rules/changes — audit log of rule-config edits."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class RuleChangeKind(str, Enum):
    creada = "creada"
    editada = "editada"
    pausada = "pausada"
    reactivada = "reactivada"
    umbral = "umbral"


class RuleChangeOut(BaseModel):
    id: str
    ts: datetime
    actor: str
    rule_code: str
    rule_name: str
    kind: RuleChangeKind
    summary: str
    before_value: str | None = None
    after_value: str | None = None
