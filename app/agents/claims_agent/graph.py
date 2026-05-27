"""Build the claims-agent LangGraph (ReAct loop).

Shape:
    START → react_step → (continue → react_step | finish → END)
                     ↑__________________|

Each `react_step` is one LLM-driven reasoning iteration: pick a tool + args,
observe, append to scratchpad. The loop exits when the LLM emits `action=finish`
OR `step_count >= max_react_steps` (safety bound).

The final NL composition (token-streamed) happens in `AskAgent._compose_stream`
AFTER the graph completes — not as a graph node, so we can use `llm.stream()`
without faking it through LangGraph events.
"""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.claims_agent.dependencies import ClaimsAgentDeps
from app.agents.claims_agent.nodes import make_react_step
from app.agents.claims_agent.state import ClaimsAgentState


def _continue_or_finish(state: ClaimsAgentState) -> str:
    return "end" if state.get("finished") else "loop"


def build_graph(deps: ClaimsAgentDeps) -> Any:
    g = StateGraph(ClaimsAgentState)
    g.add_node("react_step", make_react_step(deps))

    g.add_edge(START, "react_step")
    g.add_conditional_edges(
        "react_step",
        _continue_or_finish,
        {"loop": "react_step", "end": END},
    )
    return g.compile()
