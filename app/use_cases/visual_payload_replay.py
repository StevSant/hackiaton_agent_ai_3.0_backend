"""Map a legacy persisted `chart_payload` (single chart) to the new
`visual_payload` shape (a list of AgentVisual dicts). Pure — no I/O."""

from __future__ import annotations

from typing import Any


def legacy_chart_to_visuals(chart_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not chart_payload:
        return []
    return [{"kind": "chart", "data": chart_payload}]
