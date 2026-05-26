from typing import Any

from pydantic import BaseModel


class AgentStepData(BaseModel):
    node: str
    meta: dict[str, Any] | None = None
