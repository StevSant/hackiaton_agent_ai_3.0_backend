from typing import Literal

from pydantic import BaseModel

from app.schemas.chat.stream.tool_result_data import ToolResultData


class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    data: ToolResultData
