"""Deterministic builder: (tool_results + VisualPlan) -> list[AgentVisual].

Each PlannedVisual names a tool_ref (call_id) and a format. We dispatch on
(tool, format) and build the matching AgentVisual. Combos the data can't
support are skipped (logged) — never fabricated. Tier strings come from data.
"""

from __future__ import annotations

import logging
from typing import Any

from app.schemas.chat.stream.chart_data import ChartData, ChartSeries, ChartType
from app.schemas.chat.stream.visual import (
    AgentVisual,
    ChartVisual,
    GaugeVisual,
    KpiItem,
    KpiVisual,
    TableColumn,
    TableVisual,
)
from app.schemas.visual_plan import VisualPlan

logger = logging.getLogger(__name__)

_ALL_CHART_TYPES: list[ChartType] = [
    "bar",
    "horizontal_bar",
    "line",
    "pie",
    "doughnut",
    "scatter",
    "stacked_tier",
    "dotplot",
]


def _fmt_money(raw: Any) -> str:
    try:
        return f"USD {float(raw):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _claim_meta(c: dict[str, Any]) -> dict[str, str]:
    """Per-point tooltip metadata for a claim — what the analyst sees on hover.

    The "Siniestro" entry doubles as the click target: the frontend resolves
    chart clicks to the first claim-id-shaped meta value (timeline charts
    label points by date, so the id must travel here).
    """
    return {
        "Siniestro": str(c.get("id") or "—"),
        "Nivel": str(c.get("nivel") or "—"),
        "Ramo": str(c.get("ramo") or "—"),
        "Ciudad": str(c.get("ciudad") or "—"),
        "Asegurado": str(c.get("asegurado") or "—"),
        "Monto reclamado": _fmt_money(c.get("monto_reclamado")),
        "Fecha": str(c.get("fecha_ocurrencia") or "—"),
        "Estado": str(c.get("estado") or "—"),
    }


def build_visuals(
    tool_results: list[dict[str, Any]],
    plan: VisualPlan,
    message_id: str,
) -> list[AgentVisual]:
    """Map (tool_results + VisualPlan) -> list[AgentVisual].

    Looks each PlannedVisual.tool_ref up by call_id, dispatches on (tool,
    format), and skips combos the data can't support. Never fabricates data.
    """
    by_ref = {tr.get("call_id", ""): tr for tr in tool_results}
    out: list[AgentVisual] = []
    for pv in plan.visuals:
        tr = by_ref.get(pv.tool_ref)
        if tr is None or not isinstance(tr.get("result"), dict):
            logger.info("visual skipped: unknown tool_ref %s", pv.tool_ref)
            continue
        visual = _build_one(tr["tool"], pv.format, pv.title, tr["result"], message_id)
        if visual is None:
            logger.info(
                "visual skipped: %s does not support %s", tr.get("tool"), pv.format
            )
            continue
        out.append(visual)
    return out


def _build_one(
    tool: str,
    fmt: str,
    title: str | None,
    result: dict[str, Any],
    message_id: str,
) -> AgentVisual | None:
    if tool == "query_claims":
        return _from_query_claims(fmt, title, result, message_id)
    if tool == "aggregate_by_dimension":
        return _from_aggregate(fmt, title, result, message_id)
    if tool == "get_claim_detail":
        return _from_claim_detail(fmt, title, result, message_id)
    if tool == "missing_documents":
        return _from_missing_docs(fmt, title, result, message_id)
    if tool == "summarize_critical":
        return _from_summary(fmt, title, result, message_id)
    return None


def _chart(
    message_id: str,
    title: str,
    chart_type: ChartType,
    labels: list[str],
    series: list[ChartSeries],
    **extra: Any,
) -> ChartVisual:
    return ChartVisual(
        data=ChartData(
            message_id=message_id,
            title=title,
            chart_type=chart_type,
            available_types=_ALL_CHART_TYPES,
            labels=labels,
            series=series,
            **extra,
        )
    )


def _from_query_claims(
    fmt: str,
    title: str | None,
    result: dict[str, Any],
    message_id: str,
) -> AgentVisual | None:
    claims = result.get("claims") or []
    if not claims:
        return None
    ids = [str(c.get("id", "")) for c in claims]
    if fmt == "table":
        cols = [
            TableColumn(key="id", label="Siniestro", col_kind="citation"),
            TableColumn(key="nivel", label="Nivel", col_kind="tier"),
            TableColumn(key="score", label="Score", align="right", col_kind="number"),
            TableColumn(key="ramo", label="Ramo"),
            TableColumn(key="ciudad", label="Ciudad"),
            TableColumn(key="monto_reclamado", label="Monto", align="right", col_kind="money"),
        ]
        rows: list[dict[str, str | float | None]] = [
            {
                "id": c.get("id"),
                "nivel": c.get("nivel"),
                "score": c.get("score"),
                "ramo": c.get("ramo"),
                "ciudad": c.get("ciudad"),
                "monto_reclamado": _fmt_money(c.get("monto_reclamado")),
            }
            for c in claims
        ]
        return TableVisual(
            message_id=message_id,
            title=title or "Siniestros",
            columns=cols,
            rows=rows,
            citations=ids,
        )
    if fmt in ("horizontal_bar", "bar", "dotplot"):
        scores = [float(c.get("score") or 0) for c in claims]
        return _chart(
            message_id,
            title or "Score de riesgo",
            fmt,  # type: ignore[arg-type]
            ids,
            [ChartSeries(name="Score", data=scores)],
            citations=ids,
            meta=[_claim_meta(c) for c in claims],
        )
    if fmt in ("line", "scatter"):
        # Timeline view: claims ordered by fecha_ocurrencia, score on the y-axis.
        # Citations carry the claim ids (the x labels are dates, not routable ids).
        ordered = sorted(claims, key=lambda c: str(c.get("fecha_ocurrencia") or ""))
        labels = [str(c.get("fecha_ocurrencia") or "—") for c in ordered]
        scores = [float(c.get("score") or 0) for c in ordered]
        meta = [_claim_meta(c) for c in ordered]
        return _chart(
            message_id,
            title or "Línea de tiempo del riesgo",
            fmt,  # type: ignore[arg-type]
            labels,
            [ChartSeries(name="Score", data=scores)],
            citations=[str(c.get("id", "")) for c in ordered],
            meta=meta,
        )
    if fmt == "gauge" and len(claims) == 1:
        c = claims[0]
        return GaugeVisual(
            message_id=message_id,
            title=title or "Riesgo del siniestro",
            value=float(c.get("score") or 0),
            tier=c.get("nivel", "verde"),
            label=str(c.get("id", "")),
        )
    return None


def _from_aggregate(
    fmt: str,
    title: str | None,
    result: dict[str, Any],
    message_id: str,
) -> AgentVisual | None:
    rows = result.get("rows") or []
    if not rows:
        return None
    keys = [str(r.get("key", "")) for r in rows]
    counts = [float(r.get("count") or 0) for r in rows]
    cites = [str(r["example_claim_id"]) for r in rows if r.get("example_claim_id")]
    if fmt in ("bar", "horizontal_bar", "line", "pie", "doughnut", "stacked_tier"):
        # stacked_tier degrades to bar here — aggregate has no per-tier breakdown.
        ctype: ChartType = "bar" if fmt == "stacked_tier" else fmt  # type: ignore[assignment]
        return _chart(
            message_id,
            title or "Conteo por categoría",
            ctype,
            keys,
            [ChartSeries(name="Casos", data=counts)],
        )
    if fmt == "kpi":
        items = [
            KpiItem(label=str(r.get("key")), value=str(int(r.get("count") or 0)))
            for r in rows[:4]
        ]
        return KpiVisual(
            message_id=message_id,
            title=title or "Top categorías",
            items=items,
            citations=cites,
        )
    return None


def _from_claim_detail(
    fmt: str,
    title: str | None,
    result: dict[str, Any],
    message_id: str,
) -> AgentVisual | None:
    claim = result.get("claim")
    if not isinstance(claim, dict):
        return None
    if fmt == "gauge":
        return GaugeVisual(
            message_id=message_id,
            title=title or "Riesgo del siniestro",
            value=float(claim.get("score") or 0),
            tier=claim.get("nivel", "verde"),
            label=str(claim.get("id", "")),
        )
    if fmt == "kpi":
        items = [
            KpiItem(label="Score", value=str(claim.get("score", "—")), tier=claim.get("nivel")),
            KpiItem(label="Monto reclamado", value=_fmt_money(claim.get("monto_reclamado"))),
            KpiItem(label="Ramo", value=str(claim.get("ramo", "—"))),
        ]
        return KpiVisual(
            message_id=message_id,
            title=title or "Datos clave",
            items=items,
            citations=[str(claim.get("id", ""))],
        )
    return None


def _from_missing_docs(
    fmt: str,
    title: str | None,
    result: dict[str, Any],
    message_id: str,
) -> AgentVisual | None:
    claims = result.get("claims") or []
    if fmt != "table" or not claims:
        return None
    cols = [
        TableColumn(key="claim_id", label="Siniestro", col_kind="citation"),
        TableColumn(key="nivel", label="Nivel", col_kind="tier"),
        TableColumn(key="score", label="Score", align="right", col_kind="number"),
        TableColumn(key="faltantes", label="Documentos faltantes"),
    ]
    rows: list[dict[str, str | float | None]] = [
        {
            "claim_id": c.get("claim_id"),
            "nivel": c.get("nivel"),
            "score": c.get("score"),
            "faltantes": ", ".join(c.get("documentos_faltantes") or []) or "—",
        }
        for c in claims
    ]
    return TableVisual(
        message_id=message_id,
        title=title or "Documentos faltantes",
        columns=cols,
        rows=rows,
        citations=[str(c.get("claim_id", "")) for c in claims],
    )


def _from_summary(
    fmt: str,
    title: str | None,
    result: dict[str, Any],
    message_id: str,
) -> AgentVisual | None:
    s = result.get("summary")
    if not isinstance(s, dict):
        return None
    if fmt == "kpi":
        items = [
            KpiItem(label="Total", value=str(s.get("total_claims", 0))),
            KpiItem(label="Rojo", value=str(s.get("rojo_count", 0)), tier="rojo"),
            KpiItem(label="Amarillo", value=str(s.get("amarillo_count", 0)), tier="amarillo"),
            KpiItem(label="Verde", value=str(s.get("verde_count", 0)), tier="verde"),
        ]
        return KpiVisual(
            message_id=message_id,
            title=title or "Resumen de cartera",
            items=items,
        )
    if fmt in ("stacked_tier", "bar"):
        return _chart(
            message_id,
            title or "Composición por nivel",
            "stacked_tier" if fmt == "stacked_tier" else "bar",
            ["Cartera"],
            [
                ChartSeries(name="verde", data=[float(s.get("verde_count") or 0)]),
                ChartSeries(name="amarillo", data=[float(s.get("amarillo_count") or 0)]),
                ChartSeries(name="rojo", data=[float(s.get("rojo_count") or 0)]),
            ],
        )
    if fmt == "table":
        top = s.get("top_rojo") or []
        if not top:
            return None
        cols = [
            TableColumn(key="id", label="Siniestro", col_kind="citation"),
            TableColumn(key="nivel", label="Nivel", col_kind="tier"),
            TableColumn(key="score", label="Score", align="right", col_kind="number"),
        ]
        rows_top: list[dict[str, str | float | None]] = [
            {"id": c.get("id"), "nivel": c.get("nivel"), "score": c.get("score")}
            for c in top
        ]
        return TableVisual(
            message_id=message_id,
            title=title or "Casos críticos",
            columns=cols,
            rows=rows_top,
            citations=[str(c.get("id", "")) for c in top],
        )
    return None
