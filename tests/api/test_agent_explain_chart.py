"""Tests for POST /api/v1/agent/insights/explain.

Strategy mirrors test_agent_document_improve:
- Override get_current_user and get_llm with stubs; no real DB or OpenAI call.
- InMemoryFakeLLM is scripted to return a valid {explicacion_markdown} dict,
  keyed on a substring that appears in the user payload.
"""

from __future__ import annotations

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


_EXPLANATION = {
    "explicacion_markdown": (
        "La ciudad concentra alertas en el ramo vehículos. "
        "Casos como **SIN-0001** requieren revisión documental."
    ),
}


def _stub_llm() -> InMemoryFakeLLM:
    # Key on a substring that always appears in the explain_chart user payload.
    return InMemoryFakeLLM(script={"gráfico a explicar": _EXPLANATION})


_BODY = {
    "ciudad": "Guayaquil",
    "chart_id": "ramo_polar",
    "chart_kind": "polar",
    "chart_title": "Riesgo por ramo",
    "resumen": "Vehículos: 60% sospechoso (12/20 casos). Hogar: 10% (1/10).",
}


@pytest.mark.asyncio
async def test_explain_chart_returns_markdown() -> None:
    """POST /agent/insights/explain returns {explicacion_markdown} from the LLM."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user
    app.dependency_overrides[get_llm] = _stub_llm

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/agent/insights/explain", json=_BODY)

    assert response.status_code == 200, response.text
    data = response.json()
    assert isinstance(data.get("explicacion_markdown"), str)
    assert len(data["explicacion_markdown"]) > 0


@pytest.mark.asyncio
async def test_explain_chart_payload_carries_numbers() -> None:
    """The chart resumen (real numbers) is threaded into the LLM user payload."""
    from app.use_cases.explain_chart import _build_user_payload

    payload = _build_user_payload(
        ciudad="Guayaquil",
        chart_kind="polar",
        chart_title="Riesgo por ramo",
        resumen="Vehículos: 60% sospechoso (12/20 casos).",
    )
    assert "Vehículos: 60% sospechoso (12/20 casos)." in payload
    assert "Guayaquil" in payload


@pytest.mark.asyncio
async def test_explain_chart_empty_resumen_returns_422() -> None:
    """An empty resumen is rejected by validation (422, not 500)."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user
    app.dependency_overrides[get_llm] = _stub_llm

    body = {**_BODY, "resumen": ""}

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/agent/insights/explain", json=body)

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_explain_chart_requires_auth() -> None:
    """POST /agent/insights/explain returns 401/403 without an auth token."""
    from app.core.config import settings

    if not settings.AUTH_ENABLED:
        pytest.skip("AUTH_ENABLED=false — auth gate not active")

    app = create_app()

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/agent/insights/explain", json=_BODY)

    assert response.status_code in (401, 403), response.text


@pytest.mark.asyncio
async def test_explain_chart_use_case_with_fake_llm() -> None:
    """Unit-test: explain_chart use case returns ChartExplanation via InMemoryFakeLLM."""
    from app.use_cases.explain_chart import ChartExplanation, explain_chart

    fake_llm = InMemoryFakeLLM(script={"gráfico a explicar": _EXPLANATION})

    result = await explain_chart(
        ciudad="Guayaquil",
        chart_kind="polar",
        chart_title="Riesgo por ramo",
        resumen="Vehículos: 60% sospechoso (12/20 casos).",
        llm=fake_llm,
        llm_model="gpt-4o-mini",
    )

    assert isinstance(result, ChartExplanation)
    assert isinstance(result.explicacion_markdown, str)
    assert len(result.explicacion_markdown) > 0
