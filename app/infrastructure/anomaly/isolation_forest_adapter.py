"""IsolationForest `AnomalyDetector` impl — loads joblib artifact, returns score.

Model artifact: `data/models/anomaly_iforest.joblib`. Trained offline in
`notebooks/02_modelo_fraude.ipynb` (V5). Loaded once at app startup.

`score` follows the sklearn convention: lower = more anomalous. We surface this
verbatim and let the UI map to a human label ("indicador de anomalía").

`nearest_normal_claim_id` is populated when a ``NearestNormalIndex`` sidecar
is provided (trained on the ``etiqueta_fraude_simulada == 0`` subset). Without
the sidecar the field stays None and the UI hides the contrast widget.
"""

from __future__ import annotations

import asyncio

from app.domain.anomaly import AnomalyDetector
from app.domain.anomaly.types import AnomalyResult
from app.infrastructure.anomaly.nearest_normal_index import NearestNormalIndex


class IsolationForestDetector(AnomalyDetector):
    """`AnomalyDetector` impl backed by a joblib-saved sklearn IsolationForest."""

    def __init__(
        self,
        model_path: str,
        *,
        nearest_normal: NearestNormalIndex | None = None,
    ) -> None:
        import joblib

        self._model = joblib.load(model_path)
        names = getattr(self._model, "feature_names_in_", None)
        self._feature_names: list[str] = list(names) if names is not None else []
        self._nearest_normal = nearest_normal

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    async def score(self, features: dict[str, float]) -> AnomalyResult:
        return await asyncio.to_thread(self._score_sync, features)

    def _score_sync(self, features: dict[str, float]) -> AnomalyResult:
        import numpy as np
        import pandas as pd

        if self._feature_names:
            # Use a DataFrame so sklearn matches columns by name (and doesn't warn).
            row = pd.DataFrame(
                [[float(features.get(name, 0.0)) for name in self._feature_names]],
                columns=self._feature_names,
            )
        else:
            row = np.array([list(features.values())], dtype=np.float64)

        raw = float(self._model.score_samples(row).reshape(-1)[0])
        nearest = self._nearest_normal.nearest(features) if self._nearest_normal else None
        return AnomalyResult(score=raw, nearest_normal_claim_id=nearest)
