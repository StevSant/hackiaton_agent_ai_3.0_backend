"""Tests for the _visuals_from_tools deterministic builder (Task 4)."""

from __future__ import annotations

from app.schemas.visual_plan import PlannedVisual, VisualPlan
from app.use_cases._visuals_from_tools import build_visuals


def _tr(call_id: str, tool: str, result: dict) -> dict:
    return {"call_id": call_id, "tool": tool, "args": {}, "result": result}


# ---------------------------------------------------------------------------
# Plan's 4 required tests
# ---------------------------------------------------------------------------


def test_table_from_query_claims() -> None:
    tr = _tr(
        "c1",
        "query_claims",
        {
            "mode": "top_risk",
            "claims": [
                {
                    "id": "SIN-1",
                    "nivel": "rojo",
                    "score": 87,
                    "ramo": "Auto",
                    "ciudad": "Guayaquil",
                    "monto_reclamado": 12000.0,
                },
            ],
        },
    )
    plan = VisualPlan(visuals=[PlannedVisual(tool_ref="c1", format="table", title="Top")])
    out = build_visuals([tr], plan, "m1")
    assert len(out) == 1
    assert out[0].kind == "table"
    assert out[0].citations == ["SIN-1"]
    assert any(c.col_kind == "tier" for c in out[0].columns)


def test_gauge_from_get_claim_detail() -> None:
    tr = _tr(
        "c2",
        "get_claim_detail",
        {"found": True, "claim": {"id": "SIN-9", "score": 81, "nivel": "rojo"}},
    )
    plan = VisualPlan(visuals=[PlannedVisual(tool_ref="c2", format="gauge", title=None)])
    out = build_visuals([tr], plan, "m1")
    assert out[0].kind == "gauge"
    assert out[0].value == 81
    assert out[0].tier == "rojo"


def test_stacked_tier_from_summary() -> None:
    tr = _tr(
        "c3",
        "summarize_critical",
        {
            "summary": {
                "total_claims": 50,
                "rojo_count": 8,
                "amarillo_count": 12,
                "verde_count": 30,
                "top_rojo": [],
                "top_proveedores": [],
                "top_ramos": [],
            }
        },
    )
    plan = VisualPlan(
        visuals=[PlannedVisual(tool_ref="c3", format="stacked_tier", title=None)]
    )
    out = build_visuals([tr], plan, "m1")
    assert out[0].kind == "chart"
    assert out[0].data.chart_type == "stacked_tier"
    # Series named verde/amarillo/rojo so the frontend kit's TIER_COLOR lookup resolves
    assert {s.name for s in out[0].data.series} == {"verde", "amarillo", "rojo"}


def test_unsupported_combo_is_skipped() -> None:
    tr = _tr("c4", "missing_documents", {"tier": "rojo", "claims": []})
    plan = VisualPlan(visuals=[PlannedVisual(tool_ref="c4", format="gauge", title=None)])
    assert build_visuals([tr], plan, "m1") == []


# ---------------------------------------------------------------------------
# Additional coverage tests
# ---------------------------------------------------------------------------


def test_unknown_tool_ref_is_skipped() -> None:
    """A tool_ref not present in tool_results is silently skipped."""
    tr = _tr("c1", "query_claims", {"claims": [{"id": "SIN-1", "score": 80}]})
    plan = VisualPlan(
        visuals=[PlannedVisual(tool_ref="NONEXISTENT", format="table", title=None)]
    )
    assert build_visuals([tr], plan, "m1") == []


def test_empty_plan_returns_empty_list() -> None:
    tr = _tr("c1", "query_claims", {"claims": [{"id": "SIN-1", "score": 80}]})
    assert build_visuals([tr], VisualPlan(), "m1") == []


def test_kpi_from_summarize_critical() -> None:
    tr = _tr(
        "c5",
        "summarize_critical",
        {
            "summary": {
                "total_claims": 100,
                "rojo_count": 10,
                "amarillo_count": 20,
                "verde_count": 70,
                "top_rojo": [],
            }
        },
    )
    plan = VisualPlan(visuals=[PlannedVisual(tool_ref="c5", format="kpi", title=None)])
    out = build_visuals([tr], plan, "m2")
    assert out[0].kind == "kpi"
    labels = {item.label for item in out[0].items}
    assert {"Total", "Rojo", "Amarillo", "Verde"} == labels


def test_horizontal_bar_from_query_claims() -> None:
    tr = _tr(
        "c6",
        "query_claims",
        {
            "claims": [
                {"id": "SIN-1", "score": 90, "nivel": "rojo"},
                {"id": "SIN-2", "score": 55, "nivel": "amarillo"},
            ]
        },
    )
    plan = VisualPlan(
        visuals=[PlannedVisual(tool_ref="c6", format="horizontal_bar", title=None)]
    )
    out = build_visuals([tr], plan, "m3")
    assert out[0].kind == "chart"
    assert out[0].data.chart_type == "horizontal_bar"
    assert out[0].data.labels == ["SIN-1", "SIN-2"]


def test_gauge_query_claims_skipped_when_multiple_claims() -> None:
    """gauge from query_claims is only valid for a single-claim result."""
    tr = _tr(
        "c7",
        "query_claims",
        {
            "claims": [
                {"id": "SIN-1", "score": 90, "nivel": "rojo"},
                {"id": "SIN-2", "score": 55, "nivel": "amarillo"},
            ]
        },
    )
    plan = VisualPlan(visuals=[PlannedVisual(tool_ref="c7", format="gauge", title=None)])
    # More than 1 claim → gauge not supported → skipped
    assert build_visuals([tr], plan, "m4") == []


def test_kpi_from_claim_detail() -> None:
    tr = _tr(
        "c8",
        "get_claim_detail",
        {
            "found": True,
            "claim": {
                "id": "SIN-42",
                "score": 72,
                "nivel": "amarillo",
                "ramo": "Vida",
                "monto_reclamado": 5000.0,
            },
        },
    )
    plan = VisualPlan(visuals=[PlannedVisual(tool_ref="c8", format="kpi", title=None)])
    out = build_visuals([tr], plan, "m5")
    assert out[0].kind == "kpi"
    assert out[0].citations == ["SIN-42"]


def test_table_from_missing_docs() -> None:
    tr = _tr(
        "c9",
        "missing_documents",
        {
            "claims": [
                {
                    "claim_id": "SIN-3",
                    "nivel": "rojo",
                    "score": 88,
                    "documentos_faltantes": ["Denuncia policial", "Fotos del siniestro"],
                }
            ]
        },
    )
    plan = VisualPlan(visuals=[PlannedVisual(tool_ref="c9", format="table", title=None)])
    out = build_visuals([tr], plan, "m6")
    assert out[0].kind == "table"
    assert out[0].citations == ["SIN-3"]
    assert "Denuncia policial" in out[0].rows[0]["faltantes"]


def test_stacked_tier_values_match_summary_counts() -> None:
    """Each tier series data[0] must equal the corresponding *_count."""
    tr = _tr(
        "c10",
        "summarize_critical",
        {
            "summary": {
                "total_claims": 40,
                "rojo_count": 5,
                "amarillo_count": 15,
                "verde_count": 20,
                "top_rojo": [],
            }
        },
    )
    plan = VisualPlan(
        visuals=[PlannedVisual(tool_ref="c10", format="stacked_tier", title=None)]
    )
    out = build_visuals([tr], plan, "m7")
    series_by_name = {s.name: s.data[0] for s in out[0].data.series}
    assert series_by_name["rojo"] == 5.0
    assert series_by_name["amarillo"] == 15.0
    assert series_by_name["verde"] == 20.0


def test_aggregate_bar_from_aggregate_by_dimension() -> None:
    tr = _tr(
        "c11",
        "aggregate_by_dimension",
        {
            "dimension": "ramo",
            "rows": [
                {"key": "Auto", "count": 30},
                {"key": "Vida", "count": 12},
            ],
        },
    )
    plan = VisualPlan(visuals=[PlannedVisual(tool_ref="c11", format="bar", title=None)])
    out = build_visuals([tr], plan, "m8")
    assert out[0].kind == "chart"
    assert out[0].data.chart_type == "bar"
    assert out[0].data.labels == ["Auto", "Vida"]


def test_line_timeline_from_query_claims_orders_by_fecha() -> None:
    tr = _tr(
        "c12",
        "query_claims",
        {
            "mode": "top_risk",
            "claims": [
                {"id": "SIN-2", "nivel": "rojo", "score": 90, "fecha_ocurrencia": "2026-03-02"},
                {"id": "SIN-1", "nivel": "amarillo", "score": 55, "fecha_ocurrencia": "2026-01-15"},
            ],
        },
    )
    plan = VisualPlan(visuals=[PlannedVisual(tool_ref="c12", format="line", title=None)])
    out = build_visuals([tr], plan, "m9")
    assert out[0].kind == "chart"
    assert out[0].data.chart_type == "line"
    # Ordered chronologically by fecha_ocurrencia, not by score/rank.
    assert out[0].data.labels == ["2026-01-15", "2026-03-02"]
    assert out[0].data.series[0].data == [55.0, 90.0]
    assert out[0].data.citations == ["SIN-1", "SIN-2"]
