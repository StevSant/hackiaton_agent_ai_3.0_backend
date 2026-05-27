"""Build the claims-agent LangGraph (routing + tool dispatch only).

Shape:
    START → route → {one of 5 intent nodes} → END

The `compose` step (final NL renderer) is NOT a graph node — it lives in
`AskAgent` so it can stream tokens directly via `llm.stream()` instead of being
re-chunked after a synchronous `complete()` call. This gives real per-token UX
in the SSE response without leaking LangGraph's internal event model.

Deps (LLM, tools, prompts) are bound to the nodes via closure at build time
(`make_*` factories under `nodes/`). Each call to `build_graph(deps)` produces a
fresh compiled graph wired to those specific deps.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.claims_agent.dependencies import ClaimsAgentDeps
from app.agents.claims_agent.nodes import (
    make_aggregate,
    make_documents,
    make_explain_case,
    make_query_claims,
    make_route,
    make_summarize,
)
from app.agents.claims_agent.state import ClaimsAgentState


def _intent_branch(state: ClaimsAgentState) -> str:
    return state.get("intent") or "query_claims"


def build_graph(deps: ClaimsAgentDeps) -> Any:
    g = StateGraph(ClaimsAgentState)
    g.add_node("route", make_route(deps))
    g.add_node("query_claims", make_query_claims(deps))
    g.add_node("explain_case", make_explain_case(deps))
    g.add_node("aggregate", make_aggregate(deps))
    g.add_node("documents", make_documents(deps))
    g.add_node("summarize", make_summarize(deps))

    g.add_edge(START, "route")
    g.add_conditional_edges(
        "route",
        _intent_branch,
        {
            "query_claims": "query_claims",
            "explain_case": "explain_case",
            "aggregate": "aggregate",
            "documents": "documents",
            "summarize": "summarize",
        },
    )
    for intent_node in ("query_claims", "explain_case", "aggregate", "documents", "summarize"):
        g.add_edge(intent_node, END)
    return g.compile()
