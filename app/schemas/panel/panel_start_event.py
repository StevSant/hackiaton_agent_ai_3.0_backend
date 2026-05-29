from typing import Literal

from pydantic import BaseModel

from app.schemas.panel.panel_start_data import PanelStartData


class PanelStartEvent(BaseModel):
    type: Literal["panel_start"] = "panel_start"
    data: PanelStartData
