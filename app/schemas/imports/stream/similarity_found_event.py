from typing import Literal

from pydantic import BaseModel, Field


class SimilarClaimRef(BaseModel):
    claim_id: str
    similarity: float = Field(..., ge=0.0, le=1.0)
    snippet: str


class SimilarityFoundData(BaseModel):
    claim_id: str
    matches: list[SimilarClaimRef]   # top-3, sim >= 0.50


class SimilarityFoundEvent(BaseModel):
    type: Literal["case.similarity.found"] = "case.similarity.found"
    data: SimilarityFoundData
