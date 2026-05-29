from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.risk import Tier


class GaugeBand(BaseModel):
    to: float  # upper bound of this band on the 0..100 axis
    tier: Tier


class GaugeVisual(BaseModel):
    """A 0-100 risk dial. `bands` come from the tier config (NOT hardcoded by
    callers) — see app/domain/rules/tier.py for the canonical band edges."""

    kind: Literal["gauge"] = "gauge"
    message_id: str
    title: str
    value: float
    tier: Tier
    label: str | None = None
    bands: list[GaugeBand] = Field(default_factory=list)
