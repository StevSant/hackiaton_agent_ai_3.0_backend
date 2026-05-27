"""Tests for the ReAct multi-step loop.

Shows the killer feature: ONE analyst question → the LLM picks tools across
multiple iterations, accumulating evidence in the scratchpad before composing.
The FakeLLM uses queue-valued scripts: one entry → multiple decisions consumed
in order.
"""

import pytest

from app.agents.claims_agent import ClaimsAgentDeps
from app.agents.claims_agent.tools import (
    AggregateByDimensionTool,
    GetClaimDetailTool,
    MissingDocumentsTool,
    QueryClaimsTool,
    SummarizeCriticalTool,
)
from app.infrastructure.llm import InMemoryFakeLLM, PromptLoader
from app.schemas.agent import AgentAskRequest
from app.schemas.chat.stream import ErrorEvent, ToolCallEvent
from app.use_cases.ask_agent import AskAgent
from app.use_cases.claim_queries import InMemoryClaimQueries
from tests.fixtures.agent_claims import agent_fixtures


def _build_agent(script: dict[str, object]) -> AskAgent:
    from pathlib import Path

    prompts_dir = (
        Path(__file__).resolve().parents[2] / "app" / "agents" / "claims_agent" / "prompts"
    )
    queries = InMemoryClaimQueries(claims=agent_fixtures())
    deps = ClaimsAgentDeps(
        llm=InMemoryFakeLLM(script=script),
        llm_model="gpt-4o-mini",
        prompts=PromptLoader(base_dir=prompts_dir),
        query_claims=QueryClaimsTool(queries),
        get_claim_detail=GetClaimDetailTool(queries),
        aggregate_by_dimension=AggregateByDimensionTool(queries),
        missing_documents=MissingDocumentsTool(queries),
        summarize_critical=SummarizeCriticalTool(queries),
        max_react_steps=3,
    )
    return AskAgent(deps=deps)


@pytest.mark.asyncio
async def test_react_loop_runs_multiple_tools_in_one_turn() -> None:
    """Multi-aspect question: agent calls aggregate(proveedor) THEN aggregate(ciudad)."""
    # Queue script: 3 sequential decisions. step 1 → proveedor, step 2 → ciudad, step 3 → finish.
    # FakeLLM dequeues one per matching call.
    script = {
        "cruz": [
            {
                "thought": "primer eje: proveedor",
                "action": "use_tool",
                "tool": "aggregate_by_dimension",
                "args": {"dimension": "proveedor", "tier": "amarillo+rojo", "top_n": 5},
            },
            {
                "thought": "segundo eje: ciudad",
                "action": "use_tool",
                "tool": "aggregate_by_dimension",
                "args": {"dimension": "ciudad", "tier": "amarillo+rojo", "top_n": 5},
            },
            {
                "thought": "tengo ambos ejes",
                "action": "finish",
                "reason": "evidencia cruzada lista",
            },
        ]
    }
    agent = _build_agent(script)
    events = [
        event async for event in agent.run(
            AgentAskRequest(query="Cruz: qué proveedores y en qué ciudades concentran alertas?")
        )
    ]
    tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
    assert [tc.data.tool for tc in tool_calls] == [
        "aggregate_by_dimension",
        "aggregate_by_dimension",
    ]
    dimensions = [tc.data.args["dimension"] for tc in tool_calls]
    assert dimensions == ["proveedor", "ciudad"]
    assert not [e for e in events if isinstance(e, ErrorEvent)]


@pytest.mark.asyncio
async def test_react_loop_respects_max_steps_bound() -> None:
    """If the LLM keeps requesting tools, we hard-stop at MAX_REACT_STEPS."""
    # Script tells the LLM to ALWAYS keep calling tools. The FakeLLM's
    # auto-finish heuristic would normally end it, but a queue forces real calls.
    forever_loop_decision = {
        "thought": "sigo recolectando",
        "action": "use_tool",
        "tool": "query_claims",
        "args": {"mode": "top_risk", "top_n": 5},
    }
    script = {
        "perpetuo": [forever_loop_decision] * 5  # more than max_react_steps
    }
    agent = _build_agent(script)
    events = [
        event async for event in agent.run(
            AgentAskRequest(query="caso perpetuo de evidencia incompleta")
        )
    ]
    tool_calls = [e for e in events if isinstance(e, ToolCallEvent)]
    # max_react_steps=3 in conftest; one step decides "finish" so up to 2 tool calls.
    assert 1 <= len(tool_calls) <= 3
    assert not [e for e in events if isinstance(e, ErrorEvent)]


@pytest.mark.asyncio
async def test_react_loop_recovers_from_unknown_tool_name() -> None:
    """A bad tool name produces an error observation, then the LLM finishes."""
    script = {
        "herramienta inexistente": [
            {
                "thought": "voy a probar una herramienta que no existe",
                "action": "use_tool",
                "tool": "tool_que_no_existe",
                "args": {},
            },
            {
                "thought": "vi el error en scratchpad, mejor termino",
                "action": "finish",
                "reason": "herramienta inválida; rindo el paso",
            },
        ]
    }
    agent = _build_agent(script)
    events = [
        event async for event in agent.run(
            AgentAskRequest(query="herramienta inexistente test")
        )
    ]
    # Should NOT raise an error event (the loop catches and recovers)
    assert not [e for e in events if isinstance(e, ErrorEvent)]
    # And should NOT have emitted a tool_call event since the tool wasn't found
    assert not [e for e in events if isinstance(e, ToolCallEvent)]
