"""Wire schemas for report endpoints.

Currently exposes:
    SavingsTierBucket  — per-nivel aggregation row for the savings analysis.
    SavingsAnalysisOut — aggregate response for GET /reports/savings-analysis.
"""

from __future__ import annotations

from pydantic import BaseModel


class SavingsTierBucket(BaseModel):
    nivel: str
    casos: int
    valor_en_riesgo: float
    ahorro_potencial: float


class SavingsAnalysisOut(BaseModel):
    total_valor_en_riesgo: float
    total_ahorro_potencial: float
    casos: int
    por_nivel: list[SavingsTierBucket]
