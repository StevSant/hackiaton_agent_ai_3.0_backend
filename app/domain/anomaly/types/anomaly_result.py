from pydantic import BaseModel, Field


class AnomalyResult(BaseModel):
    """Output of `AnomalyDetector.score`.

    `score` follows the sklearn convention: lower = more anomalous, range approximately [-1, 1].
    `nearest_normal_claim_id` lets the UI show a contrasting "normal" claim
    on the detail page (root CLAUDE.md §10).
    """

    score: float = Field(..., description="sklearn convention: lower = more anomalous")
    nearest_normal_claim_id: str | None = None
