"""Train the "nearest normal claim" kNN sidecar for the anomaly adapter.

Fit ``sklearn.neighbors.NearestNeighbors`` over the ``etiqueta_fraude_simulada == 0``
subset of the training set (the "normal" anchors) so the IsolationForest adapter
can map any query feature vector to its closest known-normal claim id. This
powers the "compare with a normal claim" widget on the detail page.

Important: we only keep ORIGINAL (non-perturbed) claim ids as anchors. Variants
have ids like ``SIN-0001#v3`` which don't exist in the canonical dataset, so
returning them as a nearest_normal_claim_id would 404 from the frontend. The
``dataset_builder`` already names variants with a ``#vN`` suffix; we filter that
out here.

Artifact payload (see ``NearestNormalIndex``):

    {
        "model": NearestNeighbors,
        "claim_ids": [...],
        "feature_names": [...],
    }
"""

from __future__ import annotations

from dataclasses import dataclass

import joblib
import numpy as np
from sklearn.neighbors import NearestNeighbors

from notebooks._training.dataset_builder import TrainingDataset
from notebooks._training.paths import MODELS_DIR, NEAREST_NORMAL_INDEX_PATH


@dataclass(slots=True)
class KnnReport:
    anchors: int
    model_path: str


def train_knn(dataset: TrainingDataset, *, n_neighbors: int = 5) -> KnnReport:
    """Fit NearestNeighbors on the normal anchors and save it alongside the IF model."""
    # Anchors = original claims (no "#v" suffix) with label = 0.
    anchor_mask = np.array(
        [
            ("#v" not in cid) and (label == 0)
            for cid, label in zip(dataset.claim_ids, dataset.y, strict=True)
        ],
        dtype=bool,
    )
    if not anchor_mask.any():
        # Fallback: any label-0 row (better to ship a kNN than to ship nothing).
        anchor_mask = dataset.y == 0

    anchor_X = dataset.X[anchor_mask]
    anchor_ids = [
        cid for cid, keep in zip(dataset.claim_ids, anchor_mask, strict=True) if keep
    ]

    effective_neighbors = max(1, min(n_neighbors, len(anchor_ids)))
    model = NearestNeighbors(n_neighbors=effective_neighbors, metric="euclidean")
    model.fit(anchor_X)

    payload = {
        "model": model,
        "claim_ids": anchor_ids,
        "feature_names": list(dataset.feature_names),
    }
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, str(NEAREST_NORMAL_INDEX_PATH))

    return KnnReport(anchors=len(anchor_ids), model_path=str(NEAREST_NORMAL_INDEX_PATH))
