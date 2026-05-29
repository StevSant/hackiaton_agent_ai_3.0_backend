from typing import Literal

from pydantic import BaseModel

from app.schemas.panel.panel_done_data import PanelDoneData


class PanelDoneEvent(BaseModel):
    type: Literal["done"] = "done"
    data: PanelDoneData
