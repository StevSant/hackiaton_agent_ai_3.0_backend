"""Humanize raw model values before they reach a specialist's prompt.

The LLM can't leak `anomaly_score=-0.5339...` or `ml_probability=null` into
its citas if it only ever sees the business-Spanish reading.
"""

from __future__ import annotations

from app.core.config import settings


def probability_reading(probability: float | None) -> str:
    """0.23 → "23%"; None → "no disponible"."""
    if probability is None:
        return "no disponible"
    return f"{round(probability * 100)}%"


def anomaly_reading(score: float | None) -> str:
    """Verbal banding of the Isolation Forest score (lower = more anomalous)."""
    if score is None:
        return "no disponible"
    if score < settings.PANEL_ANOMALY_VERY_ATYPICAL:
        return "muy atípico frente al histórico"
    if score < settings.PANEL_ANOMALY_SOMEWHAT_ATYPICAL:
        return "algo atípico frente al histórico"
    return "dentro de lo normal"


def similarity_reading(similarity: float | None) -> str:
    """0.8712 → "87%"; None → "no disponible"."""
    if similarity is None:
        return "no disponible"
    return f"{round(similarity * 100)}%"
