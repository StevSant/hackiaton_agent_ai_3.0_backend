"""Shared agent test fixtures.

Wires `ClaimsAgentDeps` with `InMemoryFakeLLM` (scripted ReActDecisions) +
`InMemoryClaimQueries` (rich fixtures) + a real `PromptLoader`. The fake LLM
script maps query substrings to ReActDecision JSON (tool calls for iteration 1);
the FakeLLM auto-returns `finish` on iteration 2+ when the scratchpad has
observations — so each script entry exercises a full loop turn.
"""

from pathlib import Path

import pytest

from app.agents.claims_agent import ClaimsAgentDeps
from app.agents.claims_agent.tools import (
    AggregateByDimensionTool,
    ClaimQueries,
    GetClaimDetailTool,
    MissingDocumentsTool,
    QueryClaimsTool,
    SummarizeCriticalTool,
)
from app.infrastructure.llm import InMemoryFakeLLM, PromptLoader
from app.use_cases.ask_agent import AskAgent
from app.use_cases.claim_queries import InMemoryClaimQueries
from tests.fixtures.agent_claims import agent_fixtures


def _react(*, thought: str, tool: str, args: dict) -> dict:
    return {"thought": thought, "action": "use_tool", "tool": tool, "args": args}


def _react_script() -> dict[str, dict]:
    """Substring → ReActDecision JSON for iteration 1.

    Iteration 2+ is auto-finished by FakeLLM via the scratchpad heuristic.
    """
    return {
        # Q1 / Q12 / Q9 — ranked lists
        "mayor riesgo": _react(
            thought="ranking básico por score",
            tool="query_claims",
            args={"mode": "top_risk", "top_n": 10, "tier": "amarillo+rojo"},
        ),
        "revisar primero": _react(
            thought="recomendación priorizada",
            tool="query_claims",
            args={"mode": "recommend_review", "top_n": 5},
        ),
        "recomienda": _react(
            thought="recomendación priorizada",
            tool="query_claims",
            args={"mode": "recommend_review", "top_n": 5},
        ),
        "inicio de la póliza": _react(
            thought="FS-01 cerca del borde de vigencia",
            tool="query_claims",
            args={"mode": "near_policy_start", "top_n": 10, "window_days": 10},
        ),
        "inicio de la poliza": _react(
            thought="FS-01 cerca del borde de vigencia",
            tool="query_claims",
            args={"mode": "near_policy_start", "top_n": 10, "window_days": 10},
        ),
        # Q2 — explain by ID. Specific entries take precedence over the generic
        # "sin-" fallback because dict iteration preserves insertion order.
        "sin-1002": _react(
            thought="caso enfocado por el UI",
            tool="get_claim_detail",
            args={"claim_id": "SIN-1002"},
        ),
        "sin-1001": _react(
            thought="caso enfocado por el UI",
            tool="get_claim_detail",
            args={"claim_id": "SIN-1001"},
        ),
        "sin-": _react(
            thought="caso concreto — get_claim_detail",
            tool="get_claim_detail",
            args={"claim_id": "SIN-1001"},
        ),
        # Q3-Q6, Q8, Q10 — aggregations
        "proveedor": _react(
            thought="ranking por proveedor",
            tool="aggregate_by_dimension",
            args={"dimension": "proveedor", "tier": "amarillo+rojo", "top_n": 10},
        ),
        "ramo": _react(
            thought="distribución por ramo",
            tool="aggregate_by_dimension",
            args={"dimension": "ramo", "tier": "amarillo+rojo", "top_n": 10},
        ),
        "ciudad": _react(
            thought="distribución por ciudad",
            tool="aggregate_by_dimension",
            args={"dimension": "ciudad", "tier": "amarillo+rojo", "top_n": 10},
        ),
        "asegurado": _react(
            thought="frecuencia por asegurado",
            tool="aggregate_by_dimension",
            args={"dimension": "asegurado", "tier": "amarillo+rojo", "top_n": 10},
        ),
        "patron": _react(
            thought="patrones — agrego por proveedor",
            tool="aggregate_by_dimension",
            args={"dimension": "proveedor", "tier": "amarillo+rojo", "top_n": 10},
        ),
        "monto atipico": _react(
            thought="montos atípicos — agrego por proveedor",
            tool="aggregate_by_dimension",
            args={"dimension": "proveedor", "tier": "amarillo+rojo", "top_n": 10},
        ),
        "montos atípicos": _react(
            thought="montos atípicos — agrego por proveedor",
            tool="aggregate_by_dimension",
            args={"dimension": "proveedor", "tier": "amarillo+rojo", "top_n": 10},
        ),
        # Q7 — missing documents
        "documento": _react(
            thought="docs faltantes en casos críticos",
            tool="missing_documents",
            args={"tier": "amarillo+rojo", "top_n": 10},
        ),
        # Q11 — executive summary
        "resumen ejecutivo": _react(
            thought="snapshot global",
            tool="summarize_critical",
            args={},
        ),
    }


@pytest.fixture
def fake_llm() -> InMemoryFakeLLM:
    return InMemoryFakeLLM(
        script=_react_script(),
        default_compose=(
            "Respuesta sintética del agente — esto requiere revisión humana. "
            "Casos relevantes: {citations}."
        ),
    )


@pytest.fixture
def prompts() -> PromptLoader:
    base = Path(__file__).resolve().parents[2] / "app" / "agents" / "claims_agent" / "prompts"
    return PromptLoader(base_dir=base)


@pytest.fixture
def claim_queries() -> ClaimQueries:
    return InMemoryClaimQueries(claims=agent_fixtures())


@pytest.fixture
def agent_deps(
    fake_llm: InMemoryFakeLLM,
    prompts: PromptLoader,
    claim_queries: ClaimQueries,
) -> ClaimsAgentDeps:
    return ClaimsAgentDeps(
        llm=fake_llm,
        llm_model="gpt-4o-mini",  # unused by FakeLLM
        prompts=prompts,
        query_claims=QueryClaimsTool(claim_queries),
        get_claim_detail=GetClaimDetailTool(claim_queries),
        aggregate_by_dimension=AggregateByDimensionTool(claim_queries),
        missing_documents=MissingDocumentsTool(claim_queries),
        summarize_critical=SummarizeCriticalTool(claim_queries),
        max_react_steps=3,
    )


@pytest.fixture
def ask_agent(agent_deps: ClaimsAgentDeps) -> AskAgent:
    return AskAgent(deps=agent_deps)
