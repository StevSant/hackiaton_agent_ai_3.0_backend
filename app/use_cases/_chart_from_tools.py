"""Build a `ChartEvent` from the tool_results collected during an agent turn.

Called AFTER the compose phase finishes and BEFORE `DoneEvent` is emitted.
Returns None when no chartable tool ran, so the caller can skip the emit.

Dimension → Spanish title mapping respects the ethics rule:
  "fraude" is always qualified as "posible fraude" (CLAUDE.md §11, §2.10).
"""

from __future__ import annotations

from typing import Any

from app.schemas.chat.stream.chart_data import ChartData, ChartSeries
from app.schemas.chat.stream.chart_event import ChartEvent

_DIMENSION_TITLES: dict[str, str] = {
    "proveedor": "Alertas por proveedor",
    "ramo": "Casos por ramo",
    "ciudad": "Concentración por ciudad",
    "asegurado": "Frecuencia de reclamos por asegurado",
}


def _chart_from_aggregate(result: dict[str, Any], message_id: str) -> ChartEvent | None:
    """Build a chart from an `aggregate_by_dimension` tool result."""
    rows: list[dict[str, Any]] = result.get("rows") or []
    if not rows:
        return None

    dimension: str = result.get("dimension") or "proveedor"
    title = _DIMENSION_TITLES.get(dimension, f"Alertas por {dimension}")

    labels = [str(row.get("key", "")) for row in rows]

    # Use pct when all counts are present but pct varies meaningfully; default to count.
    # We expose count as the primary series and let the frontend choose display.
    counts = [float(row.get("count") or 0) for row in rows]
    citations = [
        str(cid)
        for row in rows
        if (cid := row.get("example_claim_id")) is not None
    ]

    return ChartEvent(
        data=ChartData(
            message_id=message_id,
            title=title,
            chart_type="bar",
            available_types=["bar", "horizontal_bar", "pie", "doughnut"],
            labels=labels,
            series=[ChartSeries(name="Casos", data=counts)],
            unit=None,
            citations=citations,
        )
    )


def _chart_from_query_claims(result: dict[str, Any], message_id: str) -> ChartEvent | None:
    """Build a chart from a `query_claims` tool result (top-risk ranked list)."""
    claims: list[dict[str, Any]] = result.get("claims") or []
    if not claims:
        return None

    # Take up to 10; they arrive pre-sorted by score descending.
    top = claims[:10]
    labels = [str(c.get("id", "")) for c in top]
    scores = [float(c.get("score") or 0) for c in top]

    if not labels:
        return None

    return ChartEvent(
        data=ChartData(
            message_id=message_id,
            title="Siniestros con mayor riesgo de posible fraude",
            chart_type="horizontal_bar",
            available_types=["horizontal_bar", "bar"],
            labels=labels,
            series=[ChartSeries(name="Score de riesgo", data=scores)],
            unit=None,
            citations=labels,
        )
    )


def maybe_build_chart(
    tool_results: list[dict[str, Any]],
    message_id: str,
) -> ChartEvent | None:
    """Inspect collected tool results and return a ChartEvent when chartable data exists.

    Priority:
      1. `aggregate_by_dimension` — richer visual; emit first when present.
      2. `query_claims` — ranked bar chart when no aggregate ran.

    Only the FIRST matching tool result produces a chart (one chart per response).
    """
    for tr in tool_results:
        tool_name: str = tr.get("tool", "")
        result: Any = tr.get("result")
        if not isinstance(result, dict):
            continue

        if tool_name == "aggregate_by_dimension":
            chart = _chart_from_aggregate(result, message_id)
            if chart is not None:
                return chart

    for tr in tool_results:
        tool_name = tr.get("tool", "")
        result = tr.get("result")
        if not isinstance(result, dict):
            continue

        if tool_name == "query_claims":
            chart = _chart_from_query_claims(result, message_id)
            if chart is not None:
                return chart

    return None
