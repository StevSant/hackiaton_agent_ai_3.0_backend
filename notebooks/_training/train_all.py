"""CLI entrypoint: build dataset, train all three models, save artifacts.

Run with ``uv run python -m notebooks._training.train_all`` from the backend repo
root. Idempotent — overwrites existing artifacts under ``data/models/``.

This is what the user/CI runs to produce the artifacts the FastAPI lifespan
loads. The Jupyter notebooks (02 / 03) call into the same modules so the
training story is reproducible from either entrypoint.
"""

from __future__ import annotations

import sys

from notebooks._training.dataset_builder import build_dataset
from notebooks._training.train_anomaly import train_anomaly
from notebooks._training.train_classifier import train_classifier
from notebooks._training.train_knn import train_knn


def main() -> int:
    print("Loading + perturbing dataset...")
    dataset = build_dataset()
    print(
        f"  rows={dataset.X.shape[0]} features={dataset.X.shape[1]} "
        f"positive_rate={dataset.positive_rate:.3f}"
    )

    print("Training classifier (LightGBM)...")
    classifier_report = train_classifier(dataset)
    print(
        f"  holdout AUC = {classifier_report.holdout_auc:.3f}\n"
        f"  CV AUC      = {classifier_report.cv_mean:.3f} +/- {classifier_report.cv_std:.3f}"
    )
    print(f"  saved -> {classifier_report.booster_path}")

    print("Training anomaly detector (IsolationForest)...")
    anomaly_report = train_anomaly(dataset)
    print(
        f"  score mean={anomaly_report.score_mean:.3f} "
        f"std={anomaly_report.score_std:.3f}"
    )
    print(f"  saved -> {anomaly_report.model_path}")

    print("Training nearest-normal kNN sidecar...")
    knn_report = train_knn(dataset)
    print(f"  anchors={knn_report.anchors}")
    print(f"  saved -> {knn_report.model_path}")

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
