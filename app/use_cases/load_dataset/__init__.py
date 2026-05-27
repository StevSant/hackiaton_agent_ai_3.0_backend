"""Dataset loader use case — ingests synthetic claims.json into Postgres."""

from app.use_cases.load_dataset.loader import load_dataset

__all__ = ["load_dataset"]
