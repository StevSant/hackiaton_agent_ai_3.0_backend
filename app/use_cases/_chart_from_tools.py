"""Build a `ChartEvent` from the tool_results collected during an agent turn.

Called AFTER the compose phase finishes and BEFORE `DoneEvent` is emitted.
Returns None when no tool requested a chart, so the caller can skip the emit.

Chart emission is **opt-in**: a chart is only built when the LLM set a
`chart_hint` on its tool call args. The hint carries the chart type the
analyst asked for (scatter / bar / pie / …). Without the hint, no chart is
emitted — keeping responses atomic.

Dimension → Spanish title mapping respects the ethics rule:
  "fraude" is always qualified as "posible fraude" (CLAUDE.md §11, §2.10).
"""

from __future__ import annotations

from typing import Any

from app.schemas.chat.stream.chart_data import ChartData, ChartSeries, ChartType
from app.schemas.chat.stream.chart_event import ChartEvent

_DIMENSION_TITLES: dict[str, str] = {
    "proveedor": "Alertas por proveedor",
    "ramo": "Casos por ramo",
    "ciudad": "Concentración por ciudad",
    "asegurado": "Frecuencia de reclamos por asegurado",
}

_DIMENSION_KEY_LABEL: dict[str, str] = {
    "proveedor": "Proveedor",
    "ramo": "Ramo",
    "ciudad": "Ciudad",
    "asegurado": "Asegurado",
}

_TIER_LABEL: dict[str, str] = {
    "verde": "🟢 Verde",
    "amarillo": "🟡 Amarillo",
    "rojo": "🔴 Rojo",
}

# Chart types we offer the user as alternatives once a chart has been requested.
# Same set for both data shapes — frontend handles fallback when a type doesn't
# fit (e.g. pie of 50 items renders as legend overflow but still works).
_ALL_TYPES: list[ChartType] = ["bar", "horizontal_bar", "scatter", "line", "pie", "doughnut"]


def _format_amount(raw: Any) -> str:
    try:
        amount = float(raw)
    except (TypeError, ValueError):
        return "—"
    return f"USD {amount:,.0f}"


def _format_tier(raw: Any) -> str:
    if not isinstance(raw, str):
        return "—"
    return _TIER_LABEL.get(raw.lower(), raw.title())


def _meta_for_claim(claim: dict[str, Any]) -> dict[str, str]:
    """Flat key/value rows shown under the claim ID in a chart tooltip."""
    return {
        "Ramo": str(claim.get("ramo") or "—"),
        "Cobertura": str(claim.get("cobertura") or "—"),
        "Asegurado": str(claim.get("asegurado") or "—"),
        "Ciudad": str(claim.get("ciudad") or "—"),
        "Fecha": str(claim.get("fecha_ocurrencia") or "—"),
        "Monto reclamado": _format_amount(claim.get("monto_reclamado")),
        "Estado": str(claim.get("estado") or "—"),
        "Nivel": _format_tier(claim.get("nivel")),
    }


def _meta_for_aggregate_row(row: dict[str, Any], dimension: str) -> dict[str, str]:
    """Flat key/value rows shown under each aggregate bar in the tooltip."""
    meta: dict[str, str] = {
        _DIMENSION_KEY_LABEL.get(dimension, dimension.title()): str(row.get("key", "—")),
        "Casos sospechosos": str(int(row.get("count") or 0)),
    }
    pct = row.get("pct")
    if isinstance(pct, (int, float)):
        meta["Porcentaje"] = f"{float(pct):.1f}%"
    example = row.get("example_claim_id")
    if example:
        meta["Ejemplo"] = str(example)
    return meta


def _read_hint(args: Any) -> dict[str, Any] | None:
    """Pull a chart_hint dict out of a tool's args, if the LLM set one."""
    if not isinstance(args, dict):
        return None
    hint = args.get("chart_hint")
    if not isinstance(hint, dict):
        return None
    return hint


def _hint_type(hint: dict[str, Any], default: ChartType) -> ChartType:
    requested = hint.get("chart_type")
    if isinstance(requested, str) and requested in _ALL_TYPES:
        return requested  # type: ignore[return-value]
    return default


def _hint_title(hint: dict[str, Any], default: str) -> str:
    custom = hint.get("title")
    if isinstance(custom, str) and custom.strip():
        return custom.strip()
    return default


def _chart_from_aggregate(
    result: dict[str, Any],
    hint: dict[str, Any],
    message_id: str,
) -> ChartEvent | None:
    """Build a chart from an `aggregate_by_dimension` tool result + a chart_hint."""
    rows: list[dict[str, Any]] = result.get("rows") or []
    if not rows:
        return None

    dimension: str = result.get("dimension") or "proveedor"
    default_title = _DIMENSION_TITLES.get(dimension, f"Alertas por {dimension}")
    title = _hint_title(hint, default_title)
    chart_type = _hint_type(hint, default="bar")

    labels = [str(row.get("key", "")) for row in rows]
    counts = [float(row.get("count") or 0) for row in rows]
    citations = [
        str(cid)
        for row in rows
        if (cid := row.get("example_claim_id")) is not None
    ]
    meta = [_meta_for_aggregate_row(row, dimension) for row in rows]

    return ChartEvent(
        data=ChartData(
            message_id=message_id,
            title=title,
            chart_type=chart_type,
            available_types=_ALL_TYPES,
            labels=labels,
            series=[ChartSeries(name="Casos", data=counts)],
            unit=None,
            citations=citations,
            meta=meta,
        )
    )


def _chart_from_query_claims(
    result: dict[str, Any],
    hint: dict[str, Any],
    message_id: str,
) -> ChartEvent | None:
    """Build a chart from a `query_claims` tool result (top-risk ranked list)."""
    claims: list[dict[str, Any]] = result.get("claims") or []
    if not claims:
        return None

    top = claims[:10]
    labels = [str(c.get("id", "")) for c in top]
    scores = [float(c.get("score") or 0) for c in top]

    if not labels:
        return None

    title = _hint_title(hint, "Siniestros con mayor riesgo de posible fraude")
    chart_type = _hint_type(hint, default="horizontal_bar")
    meta = [_meta_for_claim(c) for c in top]

    return ChartEvent(
        data=ChartData(
            message_id=message_id,
            title=title,
            chart_type=chart_type,
            available_types=_ALL_TYPES,
            labels=labels,
            series=[ChartSeries(name="Score de riesgo", data=scores)],
            unit=None,
            citations=labels,
            meta=meta,
        )
    )


def maybe_build_chart(
    tool_results: list[dict[str, Any]],
    message_id: str,
) -> ChartEvent | None:
    """Inspect collected tool results and return a ChartEvent ONLY when one of
    them carries a `chart_hint` set by the LLM. Absent the hint, no chart.

    Priority when multiple hinted tools fired:
      1. `aggregate_by_dimension` — richer visual; emit first when present.
      2. `query_claims` — ranked bar/scatter when no aggregate ran.
    """
    for tr in tool_results:
        if tr.get("tool") != "aggregate_by_dimension":
            continue
        hint = _read_hint(tr.get("args"))
        if hint is None:
            continue
        result = tr.get("result")
        if not isinstance(result, dict):
            continue
        chart = _chart_from_aggregate(result, hint, message_id)
        if chart is not None:
            return chart

    for tr in tool_results:
        if tr.get("tool") != "query_claims":
            continue
        hint = _read_hint(tr.get("args"))
        if hint is None:
            continue
        result = tr.get("result")
        if not isinstance(result, dict):
            continue
        chart = _chart_from_query_claims(result, hint, message_id)
        if chart is not None:
            return chart

    return None
