"""IsolationForest `AnomalyDetector` impl — loads joblib artifact, returns score.

Model artifact: `data/models/anomaly_iforest.joblib`. Trained offline in
`notebooks/02_modelo_fraude.ipynb` (V5). Loaded once at app startup.

`score` follows the sklearn convention: lower = more anomalous. We surface this
verbatim and let the UI map to a human label ("indicador de anomalía").

`nearest_normal_claim_id` is not computed by IsolationForest itself — it requires
a separate kNN over the same feature space. We leave it `None` here; the
`score_claim` use case (Miquel's lane) populates it from a kNN index if available.
"""

from __future__ import annotations

import asyncio

from app.domain.anomaly import AnomalyDetector as _AnomalyDetectorProto  # noqa: F401
from app.domain.anomaly.types import AnomalyResult


class IsolationForestDetector:
    """`AnomalyDetector` impl backed by a joblib-saved sklearn IsolationForest."""

    def __init__(self, model_path: str) -> None:
        import joblib

        self._model = joblib.load(model_path)
        # The training pipeline stored a sklearn estimator with `feature_names_in_`.
        names = getattr(self._model, "feature_names_in_", None)
        self._feature_names: list[str] = list(names) if names is not None else []

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    async def score(self, features: dict[str, float]) -> AnomalyResult:
        return await asyncio.to_thread(self._score_sync, features)

    def _score_sync(self, features: dict[str, float]) -> AnomalyResult:
        import numpy as np

        if self._feature_names:
            row = np.array(
                [[float(features.get(name, 0.0)) for name in self._feature_names]],
                dtype=np.float64,
            )
        else:
            # Model was trained without named features — pass the dict's values in order.
            row = np.array([list(features.values())], dtype=np.float64)

        # `score_samples` returns higher = less anomalous; we flip sign so lower = more anomalous
        # matches the sklearn `decision_function` convention.
        raw = float(self._model.score_samples(row).reshape(-1)[0])
        return AnomalyResult(score=raw, nearest_normal_claim_id=None)
