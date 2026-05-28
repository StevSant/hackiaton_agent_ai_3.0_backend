from typing import Literal

from pydantic import BaseModel, Field


class CaseCompletedData(BaseModel):
    claim_id: str
    score: int = Field(..., ge=0, le=100)
    tier: str                      # "verde" | "amarillo" | "rojo"
    persisted: bool                # True when written to DB, False on dry-run / no session
    rules_fired: int               # count of activated rules


class CaseCompletedEvent(BaseModel):
    type: Literal["case.completed"] = "case.completed"
    data: CaseCompletedData
