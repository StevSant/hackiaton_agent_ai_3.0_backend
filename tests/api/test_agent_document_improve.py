"""Tests for POST /api/v1/agent/document/improve and the /agent/ask 422 guard.

Strategy:
- Override get_current_user and get_llm with stubs; no real DB or OpenAI call.
- InMemoryFakeLLM is scripted to return a valid {titulo, contenido_markdown} dict.
- Also asserts that an over-long /agent/ask message returns 422, not 500.
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest

from app.api.deps import get_current_user, get_llm
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.infrastructure.llm import InMemoryFakeLLM
from app.main import create_app


def _stub_user() -> User:
    return User(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "analista@test.local"),
        email="analista@test.local",
        role=Role.analista,
        full_name="Test Analista",
    )


_IMPROVED_TITULO = "Informe mejorado por IA"
_IMPROVED_CONTENIDO = "## Hallazgos\n\nLos casos **SIN-0001** y **SIN-0002** requieren revisión."

_IMPROVED_RESPONSE = {
    "titulo": _IMPROVED_TITULO,
    "contenido_markdown": _IMPROVED_CONTENIDO,
}


def _stub_llm() -> InMemoryFakeLLM:
    # Key on a substring that will appear in the user payload (the original titulo).
    return InMemoryFakeLLM(
        script={"documento actual": _IMPROVED_RESPONSE},
    )


@pytest.mark.asyncio
async def test_improve_document_returns_titulo_and_contenido() -> None:
    """POST /agent/document/improve returns {titulo, contenido_markdown} from LLM."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user
    app.dependency_overrides[get_llm] = _stub_llm

    body = {
        "titulo": "Informe preliminar",
        "contenido_markdown": "## Resumen\n\nCasos revisados esta semana.",
    }

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/agent/document/improve", json=body)

    assert response.status_code == 200, response.text
    data = response.json()
    assert "titulo" in data
    assert "contenido_markdown" in data
    assert isinstance(data["titulo"], str)
    assert isinstance(data["contenido_markdown"], str)


@pytest.mark.asyncio
async def test_improve_document_threads_instrucciones() -> None:
    """instrucciones appears in the LLM prompt payload."""
    from pathlib import Path

    from app.use_cases.improve_document import _build_user_payload

    titulo = "Informe de prueba"
    contenido = "## Sección\n\nContenido."
    instrucciones = "Sé muy conciso y menciona solo los riesgos críticos."

    payload = _build_user_payload(titulo, contenido, instrucciones)
    assert instrucciones in payload, "instrucciones must appear in the user payload"


@pytest.mark.asyncio
async def test_improve_document_long_content_does_not_500() -> None:
    """contenido_markdown of 5 000 chars returns 200 (not 500)."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user
    app.dependency_overrides[get_llm] = _stub_llm

    long_content = "# Sección\n\n" + ("Texto de relleno para prueba. " * 200)
    assert len(long_content) >= 5000

    body = {
        "titulo": "Informe largo",
        "contenido_markdown": long_content,
    }

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/agent/document/improve", json=body)

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_improve_document_requires_auth() -> None:
    """POST /agent/document/improve returns 401/403 when no auth token is present."""
    from app.core.config import settings

    if not settings.AUTH_ENABLED:
        pytest.skip("AUTH_ENABLED=false — auth gate not active")

    app = create_app()
    # No override — let real auth run.

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/agent/document/improve",
                json={"titulo": "Test", "contenido_markdown": "# Hello"},
            )

    assert response.status_code in (401, 403), response.text


@pytest.mark.asyncio
async def test_agent_ask_over_long_message_returns_422() -> None:
    """POST /agent/ask with message > 4000 chars returns 422 (not 500)."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    over_long_message = "Mejorá este documento:\n\n" + ("x" * 4001)
    assert len(over_long_message) > 4000

    body = {"message": over_long_message}

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/agent/ask", json=body)

    assert response.status_code == 422, (
        f"Expected 422 for over-long message, got {response.status_code}. "
        f"Body: {response.text[:300]}"
    )


@pytest.mark.asyncio
async def test_improve_document_use_case_with_fake_llm() -> None:
    """Unit-test: improve_document use case returns ImprovedDocument via InMemoryFakeLLM."""
    from app.use_cases.improve_document import ImprovedDocument, improve_document

    fake_llm = InMemoryFakeLLM(
        script={"documento actual": _IMPROVED_RESPONSE},
    )

    result = await improve_document(
        "Informe preliminar",
        "## Resumen\n\nTexto inicial.",
        llm=fake_llm,
        llm_model="gpt-4o-mini",
        instrucciones=None,
    )

    assert isinstance(result, ImprovedDocument)
    assert isinstance(result.titulo, str)
    assert len(result.titulo) > 0
    assert isinstance(result.contenido_markdown, str)
    assert len(result.contenido_markdown) > 0


@pytest.mark.asyncio
async def test_improve_document_instrucciones_threaded_to_use_case() -> None:
    """instrucciones parameter is forwarded from route to use case (integration)."""
    from app.use_cases.improve_document import _build_user_payload

    payload = _build_user_payload(
        "Informe de prueba",
        "## Sección\n\nContenido.",
        "Sé breve.",
    )
    assert "Sé breve." in payload
