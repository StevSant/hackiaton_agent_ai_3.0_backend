"""Tests for F5 — POST /api/v1/claims/{id}/resumen/improve

Strategy:
- Override get_current_user, get_claim_queries_dep, get_reviews_store, get_llm,
  get_prompt_loader with stubs.
- Patch get_claim_detail and improve_claim_resumen at the claims-module level.
- No real DB or OpenAI call needed.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import httpx

from app.api.deps import (
    get_claim_queries_dep,
    get_current_user,
    get_llm,
    get_prompt_loader,
    get_reviews_store,
)
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.infrastructure.llm import InMemoryFakeLLM
from app.main import create_app
from app.schemas.claim import ClaimDetail, ClaimReview
from app.schemas.risk import Tier

_KNOWN_CLAIM_ID = "SIN-IMPROVE-001"
_IMPROVED_TEXT = "Resumen mejorado por la IA para el analista."


def _stub_user() -> User:
    return User(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "analista@test.local"),
        email="analista@test.local",
        role=Role.analista,
        full_name="Test Analista",
    )


def _make_claim_detail(resumen_editado: str | None = None) -> ClaimDetail:
    return ClaimDetail(
        id=_KNOWN_CLAIM_ID,
        ramo="Vehículos",
        cobertura="Responsabilidad Civil",
        asegurado="Test Asegurado",
        asegurado_id="ASE-TEST-001",
        poliza="POL-TEST-001",
        ciudad="Guayaquil",
        fecha_ocurrencia="2026-04-10",  # type: ignore[arg-type]
        fecha_reporte="2026-04-12",  # type: ignore[arg-type]
        monto_reclamado=1500.0,
        suma_asegurada=20000.0,
        estado="Reserva",
        sucursal="Guayaquil Centro",
        descripcion="Choque leve en semáforo.",
        resumen_editado=resumen_editado,
        score=15,
        nivel=Tier.verde,
        review=ClaimReview(),
    )


@pytest.mark.asyncio
async def test_improve_resumen_returns_resumen_string() -> None:
    """POST /claims/{id}/resumen/improve returns {resumen: str} with the improved text."""
    import app.api.v1.claims as _claims_module

    async def _fake_get_detail(
        queries: Any,
        claim_id: str,
        *,
        reviews_store: Any = None,
        classifier: Any = None,
        detector: Any = None,
    ) -> ClaimDetail | None:
        if claim_id == _KNOWN_CLAIM_ID:
            return _make_claim_detail()
        return None

    async def _fake_improve(
        claim: ClaimDetail,
        *,
        llm: Any,
        llm_model: str,
        instrucciones: str | None = None,
    ) -> str:
        return _IMPROVED_TEXT

    orig_get = _claims_module.get_claim_detail
    orig_improve = _claims_module.improve_claim_resumen

    _claims_module.get_claim_detail = _fake_get_detail  # type: ignore[assignment]
    _claims_module.improve_claim_resumen = _fake_improve  # type: ignore[assignment]

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user
    app.dependency_overrides[get_claim_queries_dep] = lambda: object()
    app.dependency_overrides[get_reviews_store] = lambda: object()
    app.dependency_overrides[get_llm] = lambda: InMemoryFakeLLM()

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/claims/{_KNOWN_CLAIM_ID}/resumen/improve",
                    json={},
                )
    finally:
        _claims_module.get_claim_detail = orig_get  # type: ignore[assignment]
        _claims_module.improve_claim_resumen = orig_improve  # type: ignore[assignment]

    assert response.status_code == 200, response.text
    body = response.json()
    assert "resumen" in body
    assert isinstance(body["resumen"], str)
    assert body["resumen"] == _IMPROVED_TEXT


@pytest.mark.asyncio
async def test_improve_resumen_threads_instrucciones_into_prompt() -> None:
    """instrucciones is forwarded to improve_claim_resumen use case."""
    import app.api.v1.claims as _claims_module

    captured: dict[str, Any] = {}

    async def _fake_get_detail(
        queries: Any,
        claim_id: str,
        *,
        reviews_store: Any = None,
        classifier: Any = None,
        detector: Any = None,
    ) -> ClaimDetail | None:
        return _make_claim_detail()

    async def _fake_improve(
        claim: ClaimDetail,
        *,
        llm: Any,
        llm_model: str,
        instrucciones: str | None = None,
    ) -> str:
        captured["instrucciones"] = instrucciones
        return "Resumen con instrucciones aplicadas."

    orig_get = _claims_module.get_claim_detail
    orig_improve = _claims_module.improve_claim_resumen

    _claims_module.get_claim_detail = _fake_get_detail  # type: ignore[assignment]
    _claims_module.improve_claim_resumen = _fake_improve  # type: ignore[assignment]

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user
    app.dependency_overrides[get_claim_queries_dep] = lambda: object()
    app.dependency_overrides[get_reviews_store] = lambda: object()
    app.dependency_overrides[get_llm] = lambda: InMemoryFakeLLM()

    instructions = "Sé breve y menciona solo los riesgos críticos."

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/claims/{_KNOWN_CLAIM_ID}/resumen/improve",
                    json={"instrucciones": instructions},
                )
    finally:
        _claims_module.get_claim_detail = orig_get  # type: ignore[assignment]
        _claims_module.improve_claim_resumen = orig_improve  # type: ignore[assignment]

    assert response.status_code == 200, response.text
    assert captured.get("instrucciones") == instructions


@pytest.mark.asyncio
async def test_improve_resumen_unknown_claim_returns_404() -> None:
    """POST /claims/{id}/resumen/improve returns 404 when the claim is not found."""
    import app.api.v1.claims as _claims_module

    async def _fake_get_detail(
        queries: Any,
        claim_id: str,
        *,
        reviews_store: Any = None,
        classifier: Any = None,
        detector: Any = None,
    ) -> ClaimDetail | None:
        return None

    orig_get = _claims_module.get_claim_detail
    _claims_module.get_claim_detail = _fake_get_detail  # type: ignore[assignment]

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user
    app.dependency_overrides[get_claim_queries_dep] = lambda: object()
    app.dependency_overrides[get_reviews_store] = lambda: object()
    app.dependency_overrides[get_llm] = lambda: InMemoryFakeLLM()

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/claims/SIN-MISSING-999/resumen/improve",
                    json={},
                )
    finally:
        _claims_module.get_claim_detail = orig_get  # type: ignore[assignment]

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_improve_resumen_use_case_builds_prompt_with_instrucciones() -> None:
    """Unit-test improve_claim_resumen use case: instrucciones appear in the prompt sent to LLM."""
    import json

    from app.infrastructure.llm import InMemoryFakeLLM
    from app.infrastructure.llm.types import Message
    from app.use_cases.improve_claim_resumen import improve_claim_resumen, _build_user_payload

    claim = _make_claim_detail()
    instrucciones = "Concéntrate en el riesgo financiero."

    payload = _build_user_payload(claim, instrucciones)
    assert instrucciones in payload, "instrucciones must appear in the user payload"


@pytest.mark.asyncio
async def test_improve_resumen_use_case_with_fake_llm() -> None:
    """improve_claim_resumen use case returns a non-empty string via InMemoryFakeLLM."""
    import json
    from app.infrastructure.llm import InMemoryFakeLLM
    from app.use_cases.improve_claim_resumen import improve_claim_resumen

    claim = _make_claim_detail()

    # Configure fake LLM to return a valid structured response
    fake_llm = InMemoryFakeLLM(
        script={"mejorar": json.dumps({"resumen": "Resumen generado por IA."})}
    )

    # The fake LLM matches on 'mejorar' but our payload won't contain that —
    # so it falls to the default. The default compose returns a string.
    # We need to make it return a JSON dict. Use a direct script key.
    fake_llm_direct = InMemoryFakeLLM(
        script={_KNOWN_CLAIM_ID: {"resumen": "Resumen generado por IA para el analista."}}
    )

    result = await improve_claim_resumen(
        claim,
        llm=fake_llm_direct,
        llm_model="gpt-4o-mini",
        instrucciones=None,
    )

    assert isinstance(result, str)
    assert len(result) > 0
