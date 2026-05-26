from typing import Literal

from pydantic import BaseModel

from app.schemas.chat.stream.tool_call_data import ToolCallData


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    data: ToolCallData
