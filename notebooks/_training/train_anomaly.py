"""Train IsolationForest over the training feature space and save the artifact.

The detector is unsupervised — it doesn't see ``y``. We pass the same feature
matrix as the classifier so the inference-time feature contract stays in lockstep.
Saved via joblib as that's sklearn's recommended format (and what the adapter
loads — see ``infrastructure/anomaly/isolation_forest_adapter.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from notebooks._training.dataset_builder import TrainingDataset
from notebooks._training.paths import ANOMALY_MODEL_PATH, MODELS_DIR


@dataclass(slots=True)
class AnomalyReport:
    contamination: float
    score_mean: float
    score_std: float
    model_path: str


def train_anomaly(
    dataset: TrainingDataset, *, contamination: float = 0.20, n_estimators: int = 200
) -> AnomalyReport:
    """Fit the IsolationForest, save the artifact, return summary stats."""
    # Wrap in a DataFrame so ``feature_names_in_`` is set on the fitted estimator —
    # that's what the adapter reads to reorder inference vectors deterministically.
    X_df = pd.DataFrame(dataset.X, columns=dataset.feature_names)

    model = IsolationForest(
        n_estimators=n_estimators,
        contamination=contamination,
        random_state=42,
    )
    model.fit(X_df)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, str(ANOMALY_MODEL_PATH))

    scores = model.score_samples(X_df)
    return AnomalyReport(
        contamination=contamination,
        score_mean=float(np.mean(scores)),
        score_std=float(np.std(scores)),
        model_path=str(ANOMALY_MODEL_PATH),
    )
