from typing import Literal

from pydantic import BaseModel, Field


class HeatCell(BaseModel):
    x: int = Field(ge=0)  # index into x_labels
    y: int = Field(ge=0)  # index into y_labels
    value: float


class HeatmapVisual(BaseModel):
    kind: Literal["heatmap"] = "heatmap"
    message_id: str
    title: str
    x_labels: list[str]
    y_labels: list[str]
    cells: list[HeatCell]
    value_label: str | None = None
    citations: list[str] = Field(default_factory=list)
