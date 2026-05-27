"""Wire schema for GET /insights — AI anomalies + regional + ramo distribution."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AiAnomalyOut(BaseModel):
    id: str
    title: str
    description: str
    severity: Literal["critical", "potential"]
    confidence: float


class RegionalFraudPointOut(BaseModel):
    region: str
    value: int


class ClaimTypeSliceOut(BaseModel):
    key: str
    label: str
    pct: float


class QuarterlyOutlookOut(BaseModel):
    body: str
    systematic_fraud_delta: str


class HotspotOut(BaseModel):
    sucursal: str
    count: int
    alertas: int
    avg_score: float


class IncidentOut(BaseModel):
    """One claim plotted as a point on the map.

    `sucursal` is the city the claim was filed under. Frontend resolves a stable
    intra-city offset from `id_siniestro` so each claim gets a reproducible spot
    near (but not on top of) its city center.
    """

    id_siniestro: str
    sucursal: str
    score: int
    tier: str  # "verde" | "amarillo" | "rojo"
    fecha_ocurrencia: str | None = None


class InsightsBundleOut(BaseModel):
    anomalies: list[AiAnomalyOut]
    regional_fraud: list[RegionalFraudPointOut]
    claim_type_slices: list[ClaimTypeSliceOut]
    total_claims_label: str
    quarterly_outlook: QuarterlyOutlookOut
    hotspots: list[HotspotOut]
    incidents: list[IncidentOut]
