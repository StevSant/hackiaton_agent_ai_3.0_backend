from typing import Any

from pydantic import BaseModel, Field

from app.agents.claims_agent.react.react_action import ReActAction


class ReActDecision(BaseModel):
    """Structured output the LLM produces on each ReAct step.

    Forces explicit `thought` before action — that's the "Reasoning" in ReAct.
    `tool` + `args` are required only when `action == "use_tool"`; `reason` only
    when `action == "finish"` (lets compose explain why the loop stopped).
    """

    thought: str = Field(..., description="Razonamiento breve antes de actuar")
    action: ReActAction
    tool: str | None = Field(default=None, description="Nombre exacto de la herramienta")
    args: dict[str, Any] | None = Field(
        default=None, description="Args para la herramienta (JSON match al input_schema)"
    )
    reason: str | None = Field(
        default=None, description="Por qué terminamos (cuando action=finish)"
    )
