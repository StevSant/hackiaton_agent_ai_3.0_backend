"""Task 7 — assert that AskAgent.run emits sensible VisualEvent kinds.

Four representative NL questions are tested against the full AskAgent.run
pipeline (ReAct loop → PlanVisuals → build_visuals → VisualEvent emission).
The fake LLM is extended to intercept the planner call (identified by the
"Resultados disponibles" marker in the user message) and return a scripted
VisualPlan whose tool_ref is extracted from the planner payload itself —
so the test never needs to know the dynamically-generated call_id in advance.

Scenarios:
  - Q1-style "top-risk" question    → table visual
  - Q2-style "explain SIN-XXXX"     → gauge visual
  - Q11-style "executive summary"   → kpi and/or stacked_tier visual
  - "¿cuántos críticos?" (count)    → planner returns empty → no visual
"""

from __future__ import annotations

import json
import re
from typing import Any

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
from app.infrastructure.llm.types import LLMResult, Message, ResponseFormat, ToolSpec
from app.schemas.agent import AgentAskRequest
from app.schemas.chat.stream import VisualEvent
from app.use_cases.ask_agent import AskAgent
from app.use_cases.claim_queries import InMemoryClaimQueries
from tests.fixtures.agent_claims import agent_fixtures

# ---------------------------------------------------------------------------
# Planner-aware fake LLM
# ---------------------------------------------------------------------------

class _PlannerScriptedFakeLLM(InMemoryFakeLLM):
    """Extends InMemoryFakeLLM with planner-call awareness.

    When the LLM receives a structured call whose user message contains
    "Resultados disponibles" (the planner's marker), it extracts the first
    tool_ref from the embedded JSON summary and returns a VisualPlan JSON
    using `_planner_format`.  Pass `_planner_format=None` to make the
    planner return an empty plan (no visuals).
    """

    def __init__(self, *, planner_format: str | None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._planner_format = planner_format

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[ToolSpec] | None = None,
        response_format: ResponseFormat | None = None,
    ) -> LLMResult:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )

        if response_format is not None and "Resultados disponibles" in last_user:
            # Planner call — return scripted VisualPlan.
            if self._planner_format is None:
                plan: dict[str, Any] = {"visuals": []}
            else:
                # Extract the first tool_ref embedded in the planner payload.
                match = re.search(r'"tool_ref":\s*"([^"]+)"', last_user)
                tool_ref = match.group(1) if match else ""
                plan = {
                    "visuals": [
                        {
                            "tool_ref": tool_ref,
                            "format": self._planner_format,
                            "title": None,
                        }
                    ]
                }
            content = json.dumps(plan, ensure_ascii=False)
            return LLMResult(
                message=Message(role="assistant", content=content),
                finish_reason="stop",
                input_tokens=0,
                output_tokens=len(content),
            )

        return await super().complete(
            messages, model=model, tools=tools, response_format=response_format
        )


# ---------------------------------------------------------------------------
# Shared react script (mirrors conftest._react_script — kept local so this
# test is self-contained and readable without importing from conftest)
# ---------------------------------------------------------------------------

def _react(*, thought: str, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"thought": thought, "action": "use_tool", "tool": tool, "args": args}


_BASE_SCRIPT: dict[str, Any] = {
    "mayor riesgo": _react(
        thought="ranking básico por score",
        tool="query_claims",
        args={"mode": "top_risk", "top_n": 10, "tier": "amarillo+rojo"},
    ),
    "sin-1001": _react(
        thought="caso concreto — get_claim_detail",
        tool="get_claim_detail",
        args={"claim_id": "SIN-1001"},
    ),
    "resumen ejecutivo": _react(
        thought="snapshot global",
        tool="summarize_critical",
        args={},
    ),
    # "cuántos críticos" has NO script entry → fake auto-finishes without tools
    # → planner receives no candidates → returns empty plan.
}


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_agent(planner_format: str | None) -> AskAgent:
    from pathlib import Path

    llm = _PlannerScriptedFakeLLM(
        planner_format=planner_format,
        script=dict(_BASE_SCRIPT),
        default_compose=(
            "Respuesta sintética del agente — esto requiere revisión humana. "
            "Casos relevantes: {citations}."
        ),
    )
    base = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "agents"
        / "claims_agent"
        / "prompts"
    )
    prompts = PromptLoader(base_dir=base)
    claim_queries = InMemoryClaimQueries(claims=agent_fixtures())
    deps = ClaimsAgentDeps(
        llm=llm,
        llm_model="gpt-4o-mini",
        prompts=prompts,
        query_claims=QueryClaimsTool(claim_queries),
        get_claim_detail=GetClaimDetailTool(claim_queries),
        aggregate_by_dimension=AggregateByDimensionTool(claim_queries),
        missing_documents=MissingDocumentsTool(claim_queries),
        summarize_critical=SummarizeCriticalTool(claim_queries),
        max_react_steps=3,
    )
    return AskAgent(deps=deps)


async def _collect_visuals(ask_agent: AskAgent, query: str) -> list[VisualEvent]:
    events = [
        event
        async for event in ask_agent.run(AgentAskRequest(query=query))
    ]
    return [e for e in events if isinstance(e, VisualEvent)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_top_risk_question_yields_table_visual() -> None:
    """Q1-style: "10 siniestros con mayor riesgo" → planner picks 'table'."""
    agent = _make_agent(planner_format="table")
    visuals = await _collect_visuals(
        agent, "¿Cuáles son los 10 siniestros con mayor riesgo de posible fraude?"
    )
    assert len(visuals) == 1
    assert visuals[0].data.kind == "table"


@pytest.mark.asyncio
async def test_top_risk_question_yields_horizontal_bar_visual() -> None:
    """Q1-style: same query, planner picks 'horizontal_bar' → chart visual."""
    agent = _make_agent(planner_format="horizontal_bar")
    visuals = await _collect_visuals(
        agent, "¿Cuáles son los 10 siniestros con mayor riesgo de posible fraude?"
    )
    assert len(visuals) == 1
    assert visuals[0].data.kind == "chart"
    assert visuals[0].data.data.chart_type == "horizontal_bar"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_explain_single_claim_yields_gauge_visual() -> None:
    """Q2-style: "¿Por qué SIN-1001 es alto riesgo?" → planner picks 'gauge'."""
    agent = _make_agent(planner_format="gauge")
    visuals = await _collect_visuals(
        agent, "¿Por qué SIN-1001 fue marcado como alto riesgo?"
    )
    assert len(visuals) == 1
    assert visuals[0].data.kind == "gauge"
    assert visuals[0].data.value == 88  # type: ignore[union-attr]
    assert visuals[0].data.tier == "rojo"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_executive_summary_yields_kpi_visual() -> None:
    """Q11-style: executive summary → planner picks 'kpi'."""
    agent = _make_agent(planner_format="kpi")
    visuals = await _collect_visuals(
        agent, "Genera un resumen ejecutivo de los casos críticos."
    )
    assert len(visuals) == 1
    assert visuals[0].data.kind == "kpi"


@pytest.mark.asyncio
async def test_executive_summary_yields_stacked_tier_visual() -> None:
    """Q11-style: executive summary → planner picks 'stacked_tier' → chart."""
    agent = _make_agent(planner_format="stacked_tier")
    visuals = await _collect_visuals(
        agent, "Genera un resumen ejecutivo de los casos críticos."
    )
    assert len(visuals) == 1
    assert visuals[0].data.kind == "chart"
    # series named verde/amarillo/rojo so TIER_COLOR resolves on the frontend
    series_names = {s.name for s in visuals[0].data.data.series}  # type: ignore[union-attr]
    assert series_names == {"verde", "amarillo", "rojo"}


@pytest.mark.asyncio
async def test_count_only_question_yields_no_visuals() -> None:
    """A "cuántos críticos hay?" query fires no tool → planner returns empty → no visual."""
    agent = _make_agent(planner_format="kpi")  # format irrelevant — no tool_results
    visuals = await _collect_visuals(
        agent, "¿Cuántos casos críticos hay en total?"
    )
    # No tools fired means PlanVisuals.run returns VisualPlan() before calling
    # the LLM (the candidates list is empty).
    assert visuals == []
