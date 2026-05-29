from typing import Literal

from pydantic import BaseModel

from app.schemas.chat.stream.visual import AgentVisual


class VisualEvent(BaseModel):
    type: Literal["visual"] = "visual"
    data: AgentVisual
