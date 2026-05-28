from typing import Literal

from pydantic import BaseModel


class AnomalyDetectedData(BaseModel):
    claim_id: str
    anomaly_score: float           # sklearn convention: lower = more anomalous
    nearest_normal_claim_id: str | None = None


class AnomalyDetectedEvent(BaseModel):
    type: Literal["case.anomaly.detected"] = "case.anomaly.detected"
    data: AnomalyDetectedData
