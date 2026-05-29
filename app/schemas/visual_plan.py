"""Wire shapes for the visual planner — what format(s) best present a given answer.

`VisualPlan` is the structured LLM output of `PlanVisuals`. The deterministic
builder (`use_cases/_visuals_from_tools`) turns a `VisualPlan` into concrete
`AgentVisual` instances that the agent streams as `VisualEvent`s.

`PlannedVisual` + `VisualFormat` + `VisualPlan` are a cohesive unit — acceptable
to keep in one file (like a request+response pair).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

VisualFormat = Literal[
    "bar",
    "horizontal_bar",
    "line",
    "pie",
    "doughnut",
    "scatter",
    "stacked_tier",
    "dotplot",
    "table",
    "kpi",
    "gauge",
]


class PlannedVisual(BaseModel):
    tool_ref: str = Field(description="call_id of the tool_result to visualize")
    format: VisualFormat
    title: str | None = None


class VisualPlan(BaseModel):
    visuals: list[PlannedVisual] = Field(default_factory=list)
