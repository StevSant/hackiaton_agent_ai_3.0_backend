from pydantic import TypeAdapter

from app.schemas.chat.stream import VisualEvent
from app.schemas.chat.stream.chart_data import ChartData, ChartSeries
from app.schemas.chat.stream.visual import (
    AgentVisual,
    ChartVisual,
    GaugeBand,
    GaugeVisual,
    HeatCell,
    HeatmapVisual,
    KpiItem,
    KpiVisual,
    TableColumn,
    TableVisual,
)


def test_chart_type_accepts_new_values():
    chart = ChartData(
        message_id="m1",
        title="Composición por ramo",
        chart_type="stacked_tier",
        available_types=["stacked_tier", "dotplot", "bar"],
        labels=["Auto", "Vida"],
        series=[ChartSeries(name="Rojo", data=[3.0, 1.0])],
    )
    assert chart.chart_type == "stacked_tier"


def test_chart_visual_wraps_chart_data():
    cv = ChartVisual(
        data=ChartData(
            message_id="m1",
            title="Top riesgo",
            chart_type="horizontal_bar",
            available_types=["horizontal_bar"],
            labels=["SIN-1"],
            series=[ChartSeries(name="Score", data=[87.0])],
        )
    )
    assert cv.kind == "chart"
    assert cv.data.title == "Top riesgo"


def test_table_visual_builds():
    tv = TableVisual(
        message_id="m1",
        title="Top 10 casos",
        columns=[
            TableColumn(key="id", label="Siniestro", col_kind="citation"),
            TableColumn(key="score", label="Score", align="right", col_kind="number"),
            TableColumn(key="nivel", label="Nivel", col_kind="tier"),
        ],
        rows=[{"id": "SIN-1042", "score": 87.0, "nivel": "rojo"}],
        citations=["SIN-1042"],
    )
    assert tv.kind == "table"
    assert tv.columns[0].col_kind == "citation"
    assert tv.columns[1].align == "right"


def test_kpi_visual_builds():
    kv = KpiVisual(
        message_id="m1",
        title="Resumen",
        items=[
            KpiItem(label="Críticos", value="23", delta="▲ 12%", delta_dir="up", tier="rojo"),
            KpiItem(label="En riesgo", value="USD 1.4M"),
        ],
    )
    assert kv.kind == "kpi"
    assert kv.items[0].delta_dir == "up"
    assert kv.items[1].tier is None


def test_gauge_visual_builds():
    gv = GaugeVisual(
        message_id="m1",
        title="Riesgo del siniestro",
        value=87.0,
        tier="rojo",
        label="🔴 Rojo · revisión de campo",
        bands=[
            GaugeBand(to=40.0, tier="verde"),
            GaugeBand(to=75.0, tier="amarillo"),
            GaugeBand(to=100.0, tier="rojo"),
        ],
    )
    assert gv.kind == "gauge"
    assert gv.value == 87.0
    assert gv.bands[-1].tier == "rojo"


def test_heatmap_visual_builds():
    hv = HeatmapVisual(
        message_id="m1",
        title="Concentración ciudad x ramo",
        x_labels=["Auto", "Vida"],
        y_labels=["Guayaquil", "Quito"],
        cells=[HeatCell(x=0, y=0, value=14.0), HeatCell(x=1, y=1, value=9.0)],
        value_label="Casos sospechosos",
    )
    assert hv.kind == "heatmap"
    assert hv.cells[0].value == 14.0


def test_agent_visual_discriminates_by_kind():
    adapter = TypeAdapter(AgentVisual)
    parsed = adapter.validate_python(
        {
            "kind": "kpi",
            "message_id": "m1",
            "title": "Resumen",
            "items": [{"label": "Críticos", "value": "23"}],
        }
    )
    assert parsed.kind == "kpi"
    assert parsed.items[0].label == "Críticos"


def test_visual_event_wraps_agent_visual():
    ev = VisualEvent.model_validate(
        {
            "type": "visual",
            "data": {
                "kind": "gauge",
                "message_id": "m1",
                "title": "Riesgo",
                "value": 87.0,
                "tier": "rojo",
            },
        }
    )
    assert ev.type == "visual"
    assert ev.data.kind == "gauge"
