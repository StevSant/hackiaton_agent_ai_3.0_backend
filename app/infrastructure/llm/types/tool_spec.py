from typing import Any

from pydantic import BaseModel


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]
