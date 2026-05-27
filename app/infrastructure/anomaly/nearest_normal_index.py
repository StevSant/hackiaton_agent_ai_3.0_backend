"""kNN sidecar for IsolationForest — maps a query vector to a "normal" claim id.

The notebook fits a ``sklearn.neighbors.NearestNeighbors`` on the subset of
claims with ``etiqueta_fraude_simulada == 0`` (the "normal" anchors) and
joblib-dumps it together with the parallel ``claim_ids`` array as a single dict:

    {
        "model": NearestNeighbors,
        "claim_ids": ["SIN-0001", "SIN-0007", ...],
        "feature_names": ["monto_reclamado", ...],
    }

We load that dict and expose a single ``nearest`` method that takes the feature
dict the IsolationForest already consumed and returns the matching claim id.
"""

from __future__ import annotations

from pathlib import Path


class NearestNormalIndex:
    """Wraps a joblib-saved kNN over the "normal" subset for contrast lookups."""

    def __init__(self, model_path: str) -> None:
        import joblib

        payload = joblib.load(model_path)
        if not isinstance(payload, dict):
            raise ValueError(
                f"NearestNormalIndex: expected a dict at {model_path}, got {type(payload)!r}"
            )
        try:
            self._model = payload["model"]
            self._claim_ids: list[str] = list(payload["claim_ids"])
            self._feature_names: list[str] = list(payload["feature_names"])
        except KeyError as exc:
            raise ValueError(
                f"NearestNormalIndex: missing key {exc.args[0]!r} in {model_path}"
            ) from exc

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    def nearest(self, features: dict[str, float]) -> str | None:
        """Return the id of the closest "normal" claim, or None on failure."""
        import numpy as np

        if not self._claim_ids:
            return None
        row = np.array(
            [[float(features.get(name, 0.0)) for name in self._feature_names]],
            dtype=np.float64,
        )
        _, indices = self._model.kneighbors(row, n_neighbors=1)
        idx = int(indices.reshape(-1)[0])
        if 0 <= idx < len(self._claim_ids):
            return self._claim_ids[idx]
        return None

    @staticmethod
    def file_exists(model_path: str) -> bool:
        return Path(model_path).is_file()
