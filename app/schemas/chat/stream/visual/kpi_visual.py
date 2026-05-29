from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.risk import Tier

DeltaDir = Literal["up", "down", "flat"]


class KpiItem(BaseModel):
    label: str
    value: str  # pre-formatted (e.g. "USD 1.4M", "23")
    delta: str | None = None
    delta_dir: DeltaDir | None = None
    tier: Tier | None = None


class KpiVisual(BaseModel):
    kind: Literal["kpi"] = "kpi"
    message_id: str
    title: str
    items: list[KpiItem]
    citations: list[str] = Field(default_factory=list)
