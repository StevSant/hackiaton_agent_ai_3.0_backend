from pydantic import BaseModel, Field

from app.schemas.risk import FactorContribution


class MLPrediction(BaseModel):
    """Output of `FraudClassifier.predict`: probability + top-3 SHAP factors."""

    probability: float = Field(..., ge=0.0, le=1.0)
    factors: list[FactorContribution] = Field(default_factory=list)
