from typing import Any

from pydantic import BaseModel


class ScratchpadEntry(BaseModel):
    """One step in the ReAct trace — what the LLM thought, did, and observed.

    Persisted in `ClaimsAgentState.scratchpad`. The compose prompt sees this
    trace so the final NL answer can reference the reasoning ("revisé X,
    luego Y, por eso concluyo Z"). Also serializes cleanly into tool_call /
    tool_result SSE events for the chat panel's transparency view.
    """

    step: int
    thought: str
    tool: str | None = None
    args: dict[str, Any] | None = None
    observation: Any = None
    call_id: str
