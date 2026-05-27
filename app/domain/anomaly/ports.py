from typing import Protocol, runtime_checkable

from app.domain.anomaly.types import AnomalyResult


@runtime_checkable
class AnomalyDetector(Protocol):
    """Unsupervised anomaly score (Isolation Forest by default).

    Implementations live under `app/infrastructure/anomaly/`. Surfaced on the
    detail page as "Indicador de anomalía".
    """

    async def score(self, features: dict[str, float]) -> AnomalyResult: ...
