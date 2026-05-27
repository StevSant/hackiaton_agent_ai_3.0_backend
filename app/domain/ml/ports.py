from typing import Protocol, runtime_checkable

from app.domain.ml.types import MLPrediction


@runtime_checkable
class FraudClassifier(Protocol):
    """Supervised fraud probability + per-feature explanation.

    Implementations live under `app/infrastructure/ml/`. The ML probability is
    surfaced separately from the rules score (explainability, root CLAUDE.md §2.4).
    """

    async def predict(self, features: dict[str, float]) -> MLPrediction: ...
