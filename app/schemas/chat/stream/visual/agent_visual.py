# Union assembler: imports from the sibling variant files (not the package
# __init__) to avoid a circular import, since __init__ imports this module.
from typing import Annotated

from pydantic import Field

from app.schemas.chat.stream.visual.chart_visual import ChartVisual
from app.schemas.chat.stream.visual.gauge_visual import GaugeVisual
from app.schemas.chat.stream.visual.heatmap_visual import HeatmapVisual
from app.schemas.chat.stream.visual.kpi_visual import KpiVisual
from app.schemas.chat.stream.visual.table_visual import TableVisual

AgentVisual = Annotated[
    ChartVisual | TableVisual | KpiVisual | GaugeVisual | HeatmapVisual,
    Field(discriminator="kind"),
]
