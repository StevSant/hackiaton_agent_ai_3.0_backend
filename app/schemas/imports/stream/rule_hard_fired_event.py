from typing import Any, Literal

from pydantic import BaseModel


class RuleHardFiredData(BaseModel):
    claim_id: str
    code: str                      # e.g. "RF-01"
    tier_hint: str                 # "rojo" | "amarillo"
    evidence: dict[str, Any]


class RuleHardFiredEvent(BaseModel):
    type: Literal["case.rule.hard.fired"] = "case.rule.hard.fired"
    data: RuleHardFiredData
