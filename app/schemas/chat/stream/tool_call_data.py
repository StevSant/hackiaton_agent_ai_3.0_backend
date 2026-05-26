from typing import Any

from pydantic import BaseModel


class ToolCallData(BaseModel):
    tool: str
    args: dict[str, Any]
    call_id: str
