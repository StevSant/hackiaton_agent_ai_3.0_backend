from typing import Literal

from pydantic import BaseModel

from app.schemas.chat.stream.chart_data import ChartData


class ChartEvent(BaseModel):
    type: Literal["chart"] = "chart"
    data: ChartData
