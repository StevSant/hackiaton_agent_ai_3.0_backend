"""LangGraph state for the claims agent (ReAct flavor).

Loop shape:
    START → react_step → (continue → react_step | finish → END)
                     ↑__________________|

Each `react_step` is one LLM call that decides "use a tool" or "finish".
List-typed channels (`scratchpad`, `tool_results`, `citations`) use `operator.add`
as their reducer so each node return APPENDS instead of replacing — the loop
accumulates the reasoning trace across iterations.

Per backend CLAUDE.md §5: `TypedDict` with explicit reducers — never a free-form dict.
"""

from operator import add
from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class ToolResult(TypedDict):
    tool: str
    call_id: str
    args: dict[str, Any]
    result: Any


class ClaimsAgentState(TypedDict, total=False):
    """Shared state across all claims-agent nodes.

    `total=False` so each node can return a partial dict. List channels use the
    `operator.add` reducer (append semantics).
    """

    query: str
    context: dict[str, Any] | None  # e.g. {"focus_claim_id": "SIN-0042"}

    # ReAct loop state — accumulated across iterations
    step_count: int  # last writer wins (we always set absolute value)
    scratchpad: Annotated[list[dict[str, Any]], add]  # ScratchpadEntry.model_dump()
    tool_results: Annotated[list[ToolResult], add]
    citations: Annotated[list[str], add]

    # Termination flag — flipped by react_step when the LLM picks `finish`
    # or we hit MAX_REACT_STEPS.
    finished: bool

    # Standard LangGraph message log (unused today; reserved for future memory).
    messages: Annotated[list[Any], add_messages]
