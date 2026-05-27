"""Smoke test for `POST /api/v1/agent/ask` — exercises the SSE wiring end-to-end.

Forces `LLM_PROVIDER=fake` via dependency override so the test never hits OpenAI.
Drains the SSE stream, parses each `data: <json>` line, and asserts the shape.
"""

import json
import uuid

import httpx
import pytest

from app.agents.claims_agent import ClaimsAgentDeps
from app.agents.claims_agent.tools import (
    AggregateByDimensionTool,
    GetClaimDetailTool,
    MissingDocumentsTool,
    QueryClaimsTool,
    SummarizeCriticalTool,
)
from app.api.deps import get_ask_agent, get_current_user
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.infrastructure.llm import InMemoryFakeLLM, PromptLoader
from app.main import create_app
from app.use_cases.ask_agent import AskAgent
from app.use_cases.claim_queries import InMemoryClaimQueries
from tests.fixtures.agent_claims import agent_fixtures


def _stub_user() -> User:
    return User(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "analista@test.local"),
        email="analista@test.local",
        role=Role.analista,
        full_name="Test Analista",
    )


def _make_fake_ask_agent() -> AskAgent:
    queries = InMemoryClaimQueries(claims=agent_fixtures())
    # Script a tool decision for the smoke-test query so the loop calls a tool.
    fake_llm = InMemoryFakeLLM(
        script={
            "proveedor": {
                "thought": "ranking por proveedor",
                "action": "use_tool",
                "tool": "aggregate_by_dimension",
                "args": {"dimension": "proveedor", "tier": "amarillo+rojo", "top_n": 10},
            }
        }
    )
    deps = ClaimsAgentDeps(
        llm=fake_llm,
        llm_model="gpt-4o-mini",
        prompts=PromptLoader(
            base_dir=__import__("pathlib").Path(__file__).resolve().parents[2]
            / "app"
            / "agents"
            / "claims_agent"
            / "prompts"
        ),
        query_claims=QueryClaimsTool(queries),
        get_claim_detail=GetClaimDetailTool(queries),
        aggregate_by_dimension=AggregateByDimensionTool(queries),
        missing_documents=MissingDocumentsTool(queries),
        summarize_critical=SummarizeCriticalTool(queries),
    )
    return AskAgent(deps=deps)


@pytest.mark.asyncio
async def test_agent_ask_endpoint_streams_sse_events() -> None:
    app = create_app()
    app.dependency_overrides[get_ask_agent] = _make_fake_ask_agent
    app.dependency_overrides[get_current_user] = _stub_user

    # `httpx.ASGITransport` does not run FastAPI's lifespan — wrap the client
    # block in the app's lifespan context so dependency-injection paths that
    # read from `app.state` work like they do under uvicorn.
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/agent/ask",
                json={"message": "¿Qué proveedores concentran más alertas?"},
            )
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")

            events: list[dict] = []
            for raw in response.text.splitlines():
                if not raw.startswith("data: "):
                    continue
                events.append(json.loads(raw[len("data: ") :]))

    types = [e["type"] for e in events]
    assert "agent_step" in types
    assert "tool_call" in types
    assert "tool_result" in types
    assert types[-1] == "done"
    # No error events on the golden path
    assert "error" not in types
