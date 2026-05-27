"""Shared agent test fixtures.

Wires a `ClaimsAgentDeps` with `InMemoryFakeLLM` (scripted intents) +
`InMemoryClaimQueries` (rich fixtures) + `PromptLoader` pointing at the real
prompts directory. The fake LLM script maps query substrings to `{"intent": ...}`
JSON objects — covering the 12 NL questions.
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


def _intent_script() -> dict[str, dict[str, str]]:
    """Substring → IntentChoice JSON. First match wins (case-insensitive)."""
    return {
        # explain_case — match the SIN-XXXX pattern via any explicit ID phrase
        "sin-": {"intent": "explain_case"},
        # aggregate
        "proveedor": {"intent": "aggregate"},
        "ramo": {"intent": "aggregate"},
        "ciudad": {"intent": "aggregate"},
        "asegurado": {"intent": "aggregate"},
        "patron": {"intent": "aggregate"},
        "monto atipico": {"intent": "aggregate"},
        "montos atípicos": {"intent": "aggregate"},
        # documents
        "documento": {"intent": "documents"},
        # summarize
        "resumen ejecutivo": {"intent": "summarize"},
        # query_claims — generic ranked lists / near policy start
        "mayor riesgo": {"intent": "query_claims"},
        "inicio de la poliza": {"intent": "query_claims"},
        "inicio de la póliza": {"intent": "query_claims"},
        "revisar primero": {"intent": "query_claims"},
        "recomienda": {"intent": "query_claims"},
    }


@pytest.fixture
def fake_llm() -> InMemoryFakeLLM:
    return InMemoryFakeLLM(
        script=_intent_script(),
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
        llm_model="gpt-4o-mini",  # not used by FakeLLM
        prompts=prompts,
        query_claims=QueryClaimsTool(claim_queries),
        get_claim_detail=GetClaimDetailTool(claim_queries),
        aggregate_by_dimension=AggregateByDimensionTool(claim_queries),
        missing_documents=MissingDocumentsTool(claim_queries),
        summarize_critical=SummarizeCriticalTool(claim_queries),
    )


@pytest.fixture
def ask_agent(agent_deps: ClaimsAgentDeps) -> AskAgent:
    return AskAgent(deps=agent_deps)
