"""Tests for POST /api/v1/agent/ask carrying an attached `document_context`.

The frontend's "Mejorar con IA" on a document now rides the MAIN agent: the user
types a short instruction in `message`, and the full document markdown travels in
`document_context` so it never hits the 4000-char `message` cap.

Strategy: override get_ask_agent + get_current_user; InMemoryFakeLLM scripts a
`crear_documento` ReAct decision keyed on the injected "documento actual" section.
No real OpenAI / DB calls.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx
import pytest

from app.agents.claims_agent import ClaimsAgentDeps
from app.agents.claims_agent.tools import (
    AggregateByDimensionTool,
    CrearDocumentoTool,
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

_IMPROVED_TITULO = "Informe de casos críticos — mejorado"
_IMPROVED_CONTENIDO = (
    "## Resumen\n\nLos casos **SIN-1001** y **SIN-1002** requieren revisión.\n\n"
    "## Recomendaciones\n\n- Priorizar la revisión documental de **SIN-1001**.\n"
)


def _stub_user() -> User:
    return User(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "analista@test.local"),
        email="analista@test.local",
        role=Role.analista,
        full_name="Test Analista",
    )


def _prompts_dir() -> Path:
    return (
        Path(__file__).resolve().parents[1].parent
        / "app"
        / "agents"
        / "claims_agent"
        / "prompts"
    )


def _make_fake_ask_agent() -> AskAgent:
    queries = InMemoryClaimQueries(claims=agent_fixtures())
    # When the LLM sees the injected "documento actual" section, decide to call
    # crear_documento with the IMPROVED version of that document.
    fake_llm = InMemoryFakeLLM(
        script={
            "documento actual": {
                "thought": "El analista pide mejorar el documento adjunto. Llamo crear_documento.",
                "action": "use_tool",
                "tool": "crear_documento",
                "args": {
                    "titulo": _IMPROVED_TITULO,
                    "contenido_markdown": _IMPROVED_CONTENIDO,
                },
            }
        }
    )
    deps = ClaimsAgentDeps(
        llm=fake_llm,
        llm_model="gpt-4o-mini",
        prompts=PromptLoader(base_dir=_prompts_dir()),
        query_claims=QueryClaimsTool(queries),
        get_claim_detail=GetClaimDetailTool(queries),
        aggregate_by_dimension=AggregateByDimensionTool(queries),
        missing_documents=MissingDocumentsTool(queries),
        summarize_critical=SummarizeCriticalTool(queries),
        crear_documento=CrearDocumentoTool(),
    )
    return AskAgent(deps=deps)


def _drain_sse(text: str) -> list[dict]:
    events: list[dict] = []
    for raw in text.splitlines():
        if raw.startswith("data: "):
            events.append(json.loads(raw[len("data: ") :]))
    return events


@pytest.mark.asyncio
async def test_agent_ask_with_document_context_streams_and_emits_document() -> None:
    """POST /agent/ask with a ~3000-char document_context completes the SSE stream
    without 500 and emits a `document` event (the improved canvas content)."""
    app = create_app()
    app.dependency_overrides[get_ask_agent] = _make_fake_ask_agent
    app.dependency_overrides[get_current_user] = _stub_user

    long_doc = "## Sección inicial\n\n" + ("Texto del informe a mejorar. " * 110)
    assert len(long_doc) >= 3000

    body = {
        "message": "Mejorá el documento agregando recomendaciones",
        "document_context": {
            "titulo": "Informe preliminar",
            "contenido_markdown": long_doc,
        },
    }

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/agent/ask", json=body)

            assert response.status_code == 200, response.text
            assert response.headers["content-type"].startswith("text/event-stream")
            events = _drain_sse(response.text)

    types = [e["type"] for e in events]
    assert "error" not in types, f"unexpected error event: {events}"
    assert types[-1] == "done"
    # The improving turn must still emit a `document` event so the canvas updates.
    assert "document" in types, f"expected a document event, got types={types}"
    doc_events = [e for e in events if e["type"] == "document"]
    assert doc_events[-1]["data"]["titulo"] == _IMPROVED_TITULO


@pytest.mark.asyncio
async def test_agent_ask_accepts_large_document_context_validates() -> None:
    """The request schema accepts a large contenido_markdown (well past the 4000
    message cap) without a 422 — the document rides its own field."""
    app = create_app()
    app.dependency_overrides[get_ask_agent] = _make_fake_ask_agent
    app.dependency_overrides[get_current_user] = _stub_user

    # 20k chars — far beyond the 4000-char message cap, within the 40000 doc cap.
    big_doc = "## Informe\n\n" + ("Contenido extenso del documento. " * 600)
    assert len(big_doc) > 4000

    body = {
        "message": "Mejorá la estructura",
        "document_context": {"titulo": "Informe extenso", "contenido_markdown": big_doc},
    }

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/agent/ask", json=body)
            assert response.status_code == 200, response.text


def test_to_use_case_request_maps_document_context() -> None:
    """_to_use_case_request maps wire document_context into AgentAskContext."""
    from app.api.v1.agent import _to_use_case_request
    from app.schemas.agent import DocumentContext
    from app.schemas.chat.request import AgentAskRequest as WireAgentAskRequest

    wire = WireAgentAskRequest(
        message="Mejorá el documento",
        document_context=DocumentContext(
            titulo="Informe",
            contenido_markdown="## Resumen\n\nTexto.",
        ),
    )

    use_case_req = _to_use_case_request(wire)

    assert use_case_req.context is not None
    assert use_case_req.context.document_context is not None
    assert use_case_req.context.document_context.titulo == "Informe"
    assert use_case_req.context.document_context.contenido_markdown == "## Resumen\n\nTexto."
    assert use_case_req.context.focus_claim_id is None
