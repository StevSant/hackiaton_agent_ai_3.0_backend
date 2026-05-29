"""Train the supervised LightGBM classifier and save the Booster artifact.

The training set is the perturbed expansion of the 99 archetypes (see
``dataset_builder.build_dataset``). We hold out 20% for the final AUC report
and ALSO do stratified 5-fold CV on the remaining 80% — the small parent-set
size (99 archetypes) means a single holdout AUC has high variance, so we
report mean ± std as the headline number.

The Booster is saved in LightGBM's native text format
(``Booster.save_model(path)``), which is human-inspectable. We deliberately
avoid generic Python serializers for model artifacts (backend CLAUDE.md §2).
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split

from notebooks._training.dataset_builder import TrainingDataset
from notebooks._training.paths import FRAUD_MODEL_PATH, MODELS_DIR


@dataclass(slots=True)
class ClassifierReport:
    holdout_auc: float
    cv_aucs: list[float]
    booster_path: str

    @property
    def cv_mean(self) -> float:
        return float(np.mean(self.cv_aucs)) if self.cv_aucs else 0.0

    @property
    def cv_std(self) -> float:
        return float(np.std(self.cv_aucs)) if self.cv_aucs else 0.0


_LGB_PARAMS: dict[str, object] = {
    "objective": "binary",
    "metric": "auc",
    "learning_rate": 0.05,
    "num_leaves": 31,
    "min_data_in_leaf": 5,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.9,
    "bagging_freq": 5,
    "verbose": -1,
}


def _train_one(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    feature_names: list[str],
) -> lgb.Booster:
    dtrain = lgb.Dataset(X_train, label=y_train, feature_name=feature_names)
    dval = lgb.Dataset(
        X_val, label=y_val, reference=dtrain, feature_name=feature_names
    )
    return lgb.train(
        _LGB_PARAMS,
        dtrain,
        num_boost_round=500,
        valid_sets=[dval],
        callbacks=[lgb.early_stopping(stopping_rounds=25, verbose=False)],
    )


def train_classifier(
    dataset: TrainingDataset, *, n_splits: int = 5, holdout_frac: float = 0.20
) -> ClassifierReport:
    """Train the classifier, save the booster, and return per-fold metrics."""
    X = dataset.X
    y = dataset.y
    feature_names = dataset.feature_names

    # Final holdout split (stratified — keeps the positive rate stable).
    X_dev, X_holdout, y_dev, y_holdout = train_test_split(
        X, y, test_size=holdout_frac, stratify=y, random_state=42
    )

    # CV on the dev set — mean ± std is the headline.
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    cv_aucs: list[float] = []
    for train_idx, val_idx in skf.split(X_dev, y_dev):
        booster = _train_one(
            X_dev[train_idx],
            y_dev[train_idx],
            X_dev[val_idx],
            y_dev[val_idx],
            feature_names,
        )
        val_pred = booster.predict(X_dev[val_idx])
        cv_aucs.append(float(roc_auc_score(y_dev[val_idx], val_pred)))

    # Final model: train on full dev set with a small inner validation slice
    # for early stopping, then evaluate on the held-out 20%.
    X_inner_train, X_inner_val, y_inner_train, y_inner_val = train_test_split(
        X_dev, y_dev, test_size=0.15, stratify=y_dev, random_state=7
    )
    final = _train_one(X_inner_train, y_inner_train, X_inner_val, y_inner_val, feature_names)
    holdout_pred = final.predict(X_holdout)
    holdout_auc = float(roc_auc_score(y_holdout, holdout_pred))

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    final.save_model(str(FRAUD_MODEL_PATH))

    return ClassifierReport(
        holdout_auc=holdout_auc,
        cv_aucs=cv_aucs,
        booster_path=str(FRAUD_MODEL_PATH),
    )
