"""Build the claims-agent LangGraph (ReAct loop + conversation checkpointing).

Shape:
    START → react_step → (continue → react_step | finish → END)
                     ↑__________________|

Each `react_step` is one LLM-driven reasoning iteration. The loop exits when
`finished=True` (LLM picked `finish` OR step bound reached).

`InMemorySaver` is wired as the checkpointer so `messages` persists across
requests keyed by `thread_id` (== conversation_id from the API). The
`trim_to_last_n_turns` reducer on `messages` caps memory growth.

Final NL composition is streamed AFTER the graph completes in
`AskAgent._compose_stream` — it can't be a graph node because LangGraph nodes
return state diffs synchronously, not token streams.
"""

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.claims_agent.dependencies import ClaimsAgentDeps
from app.agents.claims_agent.nodes import make_react_step
from app.agents.claims_agent.state import ClaimsAgentState


def _continue_or_finish(state: ClaimsAgentState) -> str:
    return "end" if state.get("finished") else "loop"


def build_graph(deps: ClaimsAgentDeps, *, checkpointer: Any | None = None) -> Any:
    """Compile the agent graph.

    `checkpointer` defaults to a fresh `InMemorySaver` per build. Pass an
    explicit one (e.g. shared at app startup) to persist state across requests.
    """
    g = StateGraph(ClaimsAgentState)
    g.add_node("react_step", make_react_step(deps))
    g.add_edge(START, "react_step")
    g.add_conditional_edges(
        "react_step",
        _continue_or_finish,
        {"loop": "react_step", "end": END},
    )
    return g.compile(checkpointer=checkpointer or InMemorySaver())
