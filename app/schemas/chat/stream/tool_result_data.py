from typing import Any

from pydantic import BaseModel


class ToolResultData(BaseModel):
    call_id: str
    result: Any
