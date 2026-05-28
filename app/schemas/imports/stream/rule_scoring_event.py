from typing import Any, Literal

from pydantic import BaseModel


class RuleScoringData(BaseModel):
    claim_id: str
    code: str                      # e.g. "FS-07"
    fired: bool
    puntos: int                    # 0 when not fired
    why_not: str | None = None     # hint when not fired, None when fired
    evidence: dict[str, Any]


class RuleScoringEvent(BaseModel):
    type: Literal["case.rule.scoring.evaluated"] = "case.rule.scoring.evaluated"
    data: RuleScoringData
