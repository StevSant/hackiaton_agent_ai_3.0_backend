"""LightGBM `FraudClassifier` impl — loads native text artifact + computes SHAP.

The model artifact is `data/models/fraud_lgbm.txt` (LightGBM's native format,
inspectable text). Trained offline in `notebooks/02_modelo_fraude.ipynb` (Bryan's
lane V4). Loaded once at app startup via the FastAPI lifespan; never deserialized
from user-controlled paths (root CLAUDE.md anti-pattern §17).

`predict` returns:
  - `probability` ∈ [0, 1]
  - `factors` — top-3 features by `|shap_value|` with direction (up = pushes risk up).

The ML probability is surfaced SEPARATELY from the rules score (spec §10).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.domain.ml import (
    FraudClassifier as _FraudClassifierProto,  # noqa: F401  (interface assertion)
)
from app.domain.ml.types import MLPrediction
from app.schemas.risk import FactorContribution

if TYPE_CHECKING:
    import lightgbm as lgb


class LightGBMClassifier:
    """`FraudClassifier` impl backed by a saved LightGBM Booster."""

    def __init__(self, model_path: str) -> None:
        import lightgbm as lgb
        import shap

        self._booster: lgb.Booster = lgb.Booster(model_file=model_path)
        self._explainer = shap.TreeExplainer(self._booster)
        self._feature_names: list[str] = list(self._booster.feature_name())

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    async def predict(self, features: dict[str, float]) -> MLPrediction:
        return await asyncio.to_thread(self._predict_sync, features)

    def _predict_sync(self, features: dict[str, float]) -> MLPrediction:
        import numpy as np

        row = np.array(
            [[float(features.get(name, 0.0)) for name in self._feature_names]],
            dtype=np.float64,
        )
        prob_arr = self._booster.predict(row)
        probability = float(np.asarray(prob_arr).reshape(-1)[0])
        shap_values = self._explainer.shap_values(row)
        # binary classifier — shap may return either ndarray or [class0, class1]
        if isinstance(shap_values, list):
            sv = shap_values[1] if len(shap_values) > 1 else shap_values[0]
        else:
            sv = shap_values
        sv_row = np.asarray(sv).reshape(row.shape[0], -1)[0]

        ranked = sorted(
            zip(self._feature_names, sv_row, strict=True),
            key=lambda pair: abs(pair[1]),
            reverse=True,
        )[:3]
        factors = [
            FactorContribution(
                feature=name,
                shap_value=float(value),
                direction="up" if value >= 0 else "down",
            )
            for name, value in ranked
        ]
        return MLPrediction(probability=probability, factors=factors)
