from typing import Literal

from pydantic import BaseModel, Field

ChartType = Literal["bar", "horizontal_bar", "line", "pie", "doughnut"]


class ChartSeries(BaseModel):
    name: str
    data: list[float]


class ChartData(BaseModel):
    message_id: str
    title: str
    chart_type: ChartType
    available_types: list[ChartType]
    labels: list[str]
    series: list[ChartSeries]
    unit: str | None = None
    citations: list[str] = Field(default_factory=list)
