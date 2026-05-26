from typing import Any, Literal

from pydantic import BaseModel


class LLMEvent(BaseModel):
    type: Literal["token", "tool_call", "tool_result", "done", "error"]
    data: dict[str, Any]
