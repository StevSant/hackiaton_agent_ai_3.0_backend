from typing import Literal

from pydantic import BaseModel, Field


class MLScoredData(BaseModel):
    claim_id: str
    probability: float = Field(..., ge=0.0, le=1.0)
    top_factors: list[str]         # feature names, ranked by |shap|


class MLScoredEvent(BaseModel):
    type: Literal["case.ml.scored"] = "case.ml.scored"
    data: MLScoredData
