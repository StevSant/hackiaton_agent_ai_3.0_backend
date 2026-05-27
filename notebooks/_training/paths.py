"""Filesystem paths for the offline training pipeline.

All paths are resolved relative to the backend repo root so the notebooks can
be executed with the working directory set to either the repo root or the
``notebooks/`` directory. We don't read them from ``settings`` because the
training pipeline is decoupled from the running app (different process,
different boot story).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
"""Backend repo root (``hackiaton_agent_ai_3.0_backend/``)."""

SYNTHETIC_CLAIMS_JSON: Path = REPO_ROOT / "data" / "synthetic" / "claims.json"
"""Canonical 62-archetype dataset committed to the repo."""

MODELS_DIR: Path = REPO_ROOT / "data" / "models"
"""Where trained artifacts land. Created on first save."""

FRAUD_MODEL_PATH: Path = MODELS_DIR / "fraud_lgbm.txt"
ANOMALY_MODEL_PATH: Path = MODELS_DIR / "anomaly_iforest.joblib"
NEAREST_NORMAL_INDEX_PATH: Path = MODELS_DIR / "anomaly_knn.joblib"
