from typing import Literal

from pydantic import BaseModel

from app.schemas.chat.stream.chart_data import ChartData


class ChartVisual(BaseModel):
    """ECharts series chart. Reuses the existing ChartData payload verbatim."""

    kind: Literal["chart"] = "chart"
    data: ChartData
