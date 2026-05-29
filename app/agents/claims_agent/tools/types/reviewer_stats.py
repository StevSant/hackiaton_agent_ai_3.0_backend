"""ReviewerStats — per-analyst dictamen aggregation (A3)."""

from __future__ import annotations

from pydantic import BaseModel


class ReviewerStats(BaseModel):
    """Per-analyst dictamen aggregation for the analyze_reviewers tool."""

    analista: str  # dictaminado_by_name or dictaminado_by
    total_dictamenes: int
    confirmados: int  # outcome == confirmado_sospecha
    descartados: int  # outcome == descartado
    requiere_mas_info: int
    claim_ids: list[str]  # claims this analyst dictated (sample / all)
