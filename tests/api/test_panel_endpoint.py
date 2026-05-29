"""POST /api/v1/claims/{id}/panel streams SSE PanelStreamEvent — hermetic smoke test.

Strategy mirrors test_agent_document_docx.py and test_import_stream.py:
- Override get_current_user with a stub user (no JWT needed).
- Override get_analyze_panel with a fake AnalyzePanel built from InMemoryFakeLLM +
  InMemoryClaimQueries so the test never touches a real DB or OpenAI key.
- Assert: 200, text/event-stream, panel_start frame present, done frame present.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.api.deps import get_analyze_panel, get_current_user
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.main import create_app


def _stub_user() -> User:
    return User(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "analista@test.local"),
        email="analista@test.local",
        role=Role.analista,
        full_name="Test Analista",
    )


def _fake_analyze_panel() -> Any:
    from app.agents.fraud_panel import PANEL_ROSTER
    from app.infrastructure.llm import InMemoryFakeLLM, PromptLoader
    from app.use_cases.analyze_panel import AnalyzePanel
    from app.use_cases.claim_queries import InMemoryClaimQueries
    from tests.fixtures.claims import claim_rojo

    script: dict[str, Any] = {}
    for s in PANEL_ROSTER:
        script[f"[especialista:{s.id}] [fase:veredicto]"] = {
            "nivel": "rojo" if s.id == "reglas" else "amarillo",
            "dictamen": "posible caso para revisión",
            "puntos_clave": [f"lente {s.id}"],
            "confianza": "media",
            "citas": ["SIN-0003"],
        }
        script[f"[especialista:{s.id}] [fase:replica]"] = {
            "ajuste": "mantengo mi postura",
            "nivel_actualizado": "amarillo",
            "cambia_postura": False,
        }
    script["[fase:consenso]"] = {
        "nivel_final": "amarillo",
        "nivel_de_acuerdo": 0.75,
        "puntos_de_conflicto": ["Reglas (rojo) vs resto (amarillo)"],
        "resumen": "El caso requiere revisión humana.",
        "accion_recomendada": "Escalar a la Unidad Antifraude para revisión documental.",
        "posible_falso_positivo": False,
    }

    prompts_base = (
        Path(__file__).resolve().parents[2] / "app" / "agents" / "fraud_panel" / "prompts"
    )
    return AnalyzePanel(
        llm=InMemoryFakeLLM(script=script),
        prompts=PromptLoader(base_dir=prompts_base),
        queries=InMemoryClaimQueries(claims=[claim_rojo()]),
        model="gpt-4o-mini",
    )


def _parse_sse_events(body: str) -> list[dict]:
    events: list[dict] = []
    for line in body.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


@pytest.mark.asyncio
async def test_panel_endpoint_streams_events() -> None:
    """POST /claims/SIN-0003/panel returns 200, SSE content-type, panel_start + done."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user
    app.dependency_overrides[get_analyze_panel] = _fake_analyze_panel

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/claims/SIN-0003/panel")

        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("text/event-stream")

        events = _parse_sse_events(resp.text)
        types = [e["type"] for e in events]

        assert types[0] == "panel_start", f"First event was: {types[0]}"
        assert types[-1] == "done", f"Last event was: {types[-1]}"
        assert "agent_verdict" in types
        assert "consensus" in types
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_panel_endpoint_missing_claim_emits_error_then_done() -> None:
    """POST /claims/SIN-NOPE/panel returns 200 SSE with error then done (not found)."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user
    app.dependency_overrides[get_analyze_panel] = _fake_analyze_panel

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/api/v1/claims/SIN-NOPE/panel")

        assert resp.status_code == 200, resp.text
        events = _parse_sse_events(resp.text)
        types = [e["type"] for e in events]
        assert "error" in types
        assert types[-1] == "done"
    finally:
        app.dependency_overrides.clear()
