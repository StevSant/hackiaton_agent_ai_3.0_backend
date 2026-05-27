"""LangGraph state for the claims agent (ReAct loop + conversation memory).

Loop shape:
    START → react_step → (continue → react_step | finish → END)
                     ↑__________________|

`messages` is a multi-turn chat log persisted across requests via the LangGraph
checkpointer. The custom `trim_to_last_n_turns` reducer keeps the last N
HumanMessage exchanges intact (whole turns — never splits a ToolMessage from
its parent AIMessage).

Other list channels (`scratchpad`, `tool_results`, `citations`) use
`operator.add` so the ReAct loop accumulates across iterations WITHIN one turn.
They get reset at the start of each new turn by ask_agent's initial state.
"""

from operator import add
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage

from app.agents.claims_agent.state_reducers import trim_to_last_n_turns


class ToolResult(TypedDict):
    tool: str
    call_id: str
    args: dict[str, Any]
    result: Any


class ClaimsAgentState(TypedDict, total=False):
    """Shared state across all claims-agent nodes.

    `total=False` so each node can return a partial dict.
    """

    # Per-turn inputs (reset every request)
    query: str
    context: dict[str, Any] | None  # e.g. {"focus_claim_id": "SIN-0042"}

    # Per-turn ReAct loop state (lists APPEND across loop iterations within a turn)
    step_count: int  # last writer wins
    scratchpad: Annotated[list[dict[str, Any]], add]
    tool_results: Annotated[list[ToolResult], add]
    citations: Annotated[list[str], add]
    finished: bool

    # Multi-turn chat log (persisted by the checkpointer across requests)
    messages: Annotated[list[BaseMessage], trim_to_last_n_turns]
