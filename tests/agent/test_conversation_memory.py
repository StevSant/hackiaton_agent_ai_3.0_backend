"""Multi-turn conversation memory tests.

Verifies the LangGraph checkpointer + turn-windowing reducer keep prior turns
visible to follow-up questions when the client reuses `conversation_id`, and
that omitting `conversation_id` (or using a different one) starts fresh.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.claims_agent.dependencies import ClaimsAgentDeps
from app.agents.claims_agent.state_reducers import trim_to_last_n_turns
from app.agents.claims_agent.tools import (
    AggregateByDimensionTool,
    GetClaimDetailTool,
    MissingDocumentsTool,
    QueryClaimsTool,
    SummarizeCriticalTool,
)
from app.core.config import settings
from app.infrastructure.llm import InMemoryFakeLLM, PromptLoader
from app.schemas.agent import AgentAskRequest
from app.schemas.chat.stream import TokenEvent
from app.use_cases.ask_agent import AskAgent
from app.use_cases.claim_queries import InMemoryClaimQueries
from tests.fixtures.agent_claims import agent_fixtures


def _build_agent() -> AskAgent:
    from pathlib import Path

    prompts_dir = (
        Path(__file__).resolve().parents[2] / "app" / "agents" / "claims_agent" / "prompts"
    )
    queries = InMemoryClaimQueries(claims=agent_fixtures())
    fake_llm = InMemoryFakeLLM(
        script={
            "proveedor": {
                "thought": "agrego por proveedor",
                "action": "use_tool",
                "tool": "aggregate_by_dimension",
                "args": {"dimension": "proveedor", "tier": "amarillo+rojo", "top_n": 5},
            },
            "primera pregunta": {
                "thought": "ranking por riesgo",
                "action": "use_tool",
                "tool": "query_claims",
                "args": {"mode": "top_risk", "top_n": 5},
            },
        }
    )
    deps = ClaimsAgentDeps(
        llm=fake_llm,
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


async def _drain(agent: AskAgent, *, query: str, conversation_id: str | None = None) -> str:
    """Run a turn and return the concatenated streamed answer."""
    parts: list[str] = []
    async for event in agent.run(
        AgentAskRequest(query=query, conversation_id=conversation_id)
    ):
        if isinstance(event, TokenEvent):
            parts.append(event.data.delta)
    return "".join(parts)


@pytest.mark.asyncio
async def test_same_conversation_id_carries_messages_across_turns() -> None:
    agent = _build_agent()
    cid = "conv-test-1"
    answer_1 = await _drain(agent, query="primera pregunta sobre riesgo", conversation_id=cid)
    assert answer_1, "first turn should produce a non-empty answer"

    # Inspect the checkpointer state for this thread.
    state = await agent._graph.aget_state(
        {"configurable": {"thread_id": cid}}
    )
    messages = state.values.get("messages") or []
    # Turn 1: 1 HumanMessage + 1 AIMessage (the persisted compose output).
    assert any(isinstance(m, HumanMessage) for m in messages), (
        "the first turn's HumanMessage must persist in state"
    )
    assert any(isinstance(m, AIMessage) for m in messages), (
        "the first turn's AIMessage must persist via aupdate_state"
    )

    answer_2 = await _drain(
        agent, query="proveedor en ese caso?", conversation_id=cid
    )
    assert answer_2, "second turn should also produce an answer"

    state = await agent._graph.aget_state(
        {"configurable": {"thread_id": cid}}
    )
    final_messages = state.values.get("messages") or []
    human_count = sum(1 for m in final_messages if isinstance(m, HumanMessage))
    assert human_count == 2, (
        f"thread should have 2 HumanMessages after 2 turns, got {human_count}"
    )


@pytest.mark.asyncio
async def test_fresh_conversation_id_starts_clean() -> None:
    agent = _build_agent()
    await _drain(agent, query="primera pregunta sobre riesgo", conversation_id="conv-A")

    state_a = await agent._graph.aget_state(
        {"configurable": {"thread_id": "conv-A"}}
    )
    assert state_a.values.get("messages"), "conv-A should have messages after turn"

    # A different conversation_id sees no prior context.
    state_b = await agent._graph.aget_state(
        {"configurable": {"thread_id": "conv-B"}}
    )
    assert not state_b.values.get("messages"), "conv-B should be empty"


def test_trim_to_last_n_turns_keeps_whole_turns() -> None:
    """Unit test the reducer in isolation."""
    # Build 12 turns (12 HumanMessage + alternating AIMessage). Default cap = 8.
    history: list = []
    for i in range(12):
        history.append(HumanMessage(content=f"pregunta {i}", id=f"h-{i}"))
        history.append(AIMessage(content=f"respuesta {i}", id=f"a-{i}"))

    trimmed = trim_to_last_n_turns(existing=[], new=history)
    human_count = sum(1 for m in trimmed if isinstance(m, HumanMessage))
    assert human_count == settings.MAX_CONVERSATION_TURNS
    # Should be the LAST N (preserves the recent context, drops the oldest).
    last_human = [m for m in trimmed if isinstance(m, HumanMessage)][-1]
    assert isinstance(last_human.content, str)
    assert last_human.content == "pregunta 11"
    # Every HumanMessage must be paired with its AIMessage (no orphans).
    indices = [i for i, m in enumerate(trimmed) if isinstance(m, HumanMessage)]
    for idx in indices:
        assert idx + 1 < len(trimmed), "every HumanMessage must have a following AIMessage"
        assert isinstance(trimmed[idx + 1], AIMessage)
