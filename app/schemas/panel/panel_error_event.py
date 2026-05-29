from typing import Literal

from pydantic import BaseModel

from app.schemas.panel.panel_error_data import PanelErrorData


class PanelErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    data: PanelErrorData
