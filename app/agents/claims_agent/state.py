"""LangGraph state for the claims agent.

`route` sets `intent`; the conditional edge in `graph.py` then dispatches to one
of the 5 intent nodes; each intent node calls a tool and appends a `tool_results`
entry; finally `compose` produces the Spanish answer with citations.

Per backend CLAUDE.md §5: `TypedDict` with explicit reducers — never a free-form dict.
"""

from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph.message import add_messages

Intent = Literal["query_claims", "explain_case", "aggregate", "documents", "summarize"]


class ToolResult(TypedDict):
    tool: str
    call_id: str
    args: dict[str, Any]
    result: Any


class ClaimsAgentState(TypedDict, total=False):
    """Shared state across all claims-agent nodes.

    `total=False` so each node can return a partial dict to merge — the standard
    LangGraph pattern. `messages` uses the `add_messages` reducer.
    """

    query: str
    intent: Intent | None
    tool_results: list[ToolResult]
    citations: list[str]  # claim IDs
    messages: Annotated[list[Any], add_messages]
    context: dict[str, Any] | None  # e.g. {"focus_claim_id": "SIN-0042"}
    answer: str  # final composed Spanish answer
    message_id: str
