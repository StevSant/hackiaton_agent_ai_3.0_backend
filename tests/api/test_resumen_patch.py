"""Tests for PATCH /api/v1/claims/{id}/resumen (B1) and
GET /api/v1/claims/import/template?format=json (B4).

Strategy:
- Override get_current_user to bypass auth.
- Override _get_optional_session and get_claim_queries_dep / get_reviews_store
  with in-memory stubs so no real DB is required.
- Use an in-memory fake for update_claim_resumen and get_claim_detail at the
  module level to avoid full DB wiring.
"""

from __future__ import annotations

import uuid
from typing import Any
from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_reviews_store, get_claim_queries_dep
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.main import create_app
from app.schemas.claim import ClaimDetail, ClaimReview
from app.schemas.risk import Tier

# ---------------------------------------------------------------------------
# Shared stubs
# ---------------------------------------------------------------------------

_KNOWN_CLAIM_ID = "SIN-TEST-001"
_UNKNOWN_CLAIM_ID = "SIN-MISSING-999"


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


async def _fake_optional_session() -> AsyncIterator[AsyncSession | None]:
    yield None


# ---------------------------------------------------------------------------
# PATCH /{claim_id}/resumen — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_resumen_persists_and_returns_detail() -> None:
    """PATCH with a valid body updates resumen_editado; response contains new value."""
    import httpx

    # Patch at the claims route module level (where the name is bound after import).
    import app.api.v1.claims as _claims_module

    _persisted_resumen: dict[str, str] = {}

    async def _fake_update(session: Any, claim_id: str, resumen_editado: str) -> bool:
        if claim_id != _KNOWN_CLAIM_ID:
            return False
        _persisted_resumen[claim_id] = resumen_editado
        return True

    async def _fake_get_detail(
        queries: Any,
        claim_id: str,
        *,
        reviews_store: Any = None,
        classifier: Any = None,
        detector: Any = None,
    ) -> ClaimDetail | None:
        if claim_id != _KNOWN_CLAIM_ID:
            return None
        return _make_claim_detail(resumen_editado=_persisted_resumen.get(claim_id))

    original_update = _claims_module.update_claim_resumen
    original_get = _claims_module.get_claim_detail

    _claims_module.update_claim_resumen = _fake_update  # type: ignore[assignment]
    _claims_module.get_claim_detail = _fake_get_detail  # type: ignore[assignment]

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    from app.api.deps import _get_optional_session as _dep_sess
    from app.api.v1.claims import _get_optional_session as _route_sess

    async def _real_session_stub() -> AsyncIterator[AsyncSession | None]:
        # Yield a truthy sentinel so the 503 guard passes; fake use case ignores it.
        yield object()  # type: ignore[misc]

    app.dependency_overrides[_dep_sess] = _real_session_stub
    app.dependency_overrides[_route_sess] = _real_session_stub
    app.dependency_overrides[get_claim_queries_dep] = lambda: object()
    app.dependency_overrides[get_reviews_store] = lambda: object()

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/claims/{_KNOWN_CLAIM_ID}/resumen",
                    json={"resumen_editado": "Resumen editado por el analista."},
                )
    finally:
        _claims_module.update_claim_resumen = original_update  # type: ignore[assignment]
        _claims_module.get_claim_detail = original_get  # type: ignore[assignment]

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["resumen_editado"] == "Resumen editado por el analista."
    assert body["id"] == _KNOWN_CLAIM_ID


# ---------------------------------------------------------------------------
# PATCH /{claim_id}/resumen — 404 on unknown claim
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_resumen_unknown_claim_returns_404() -> None:
    """PATCH on a nonexistent claim_id must return 404."""
    import httpx

    import app.api.v1.claims as _claims_module

    async def _fake_update(session: Any, claim_id: str, resumen_editado: str) -> bool:
        return False  # claim not found

    original_update = _claims_module.update_claim_resumen
    _claims_module.update_claim_resumen = _fake_update  # type: ignore[assignment]

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    from app.api.deps import _get_optional_session as _dep_sess
    from app.api.v1.claims import _get_optional_session as _route_sess

    async def _real_session_stub() -> AsyncIterator[AsyncSession | None]:
        yield object()  # type: ignore[misc]

    app.dependency_overrides[_dep_sess] = _real_session_stub
    app.dependency_overrides[_route_sess] = _real_session_stub
    app.dependency_overrides[get_claim_queries_dep] = lambda: object()
    app.dependency_overrides[get_reviews_store] = lambda: object()

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.patch(
                    f"/api/v1/claims/{_UNKNOWN_CLAIM_ID}/resumen",
                    json={"resumen_editado": "Algo"},
                )
    finally:
        _claims_module.update_claim_resumen = original_update  # type: ignore[assignment]

    assert response.status_code == 404, response.text


# ---------------------------------------------------------------------------
# PATCH /{claim_id}/resumen — 422 on empty body / missing field
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_resumen_empty_body_returns_422() -> None:
    """Empty JSON body or missing required field must return 422."""
    import httpx

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    from app.api.deps import _get_optional_session as _dep_sess
    from app.api.v1.claims import _get_optional_session as _route_sess

    async def _real_session_stub() -> AsyncIterator[AsyncSession | None]:
        yield object()  # type: ignore[misc]

    app.dependency_overrides[_dep_sess] = _real_session_stub
    app.dependency_overrides[_route_sess] = _real_session_stub
    app.dependency_overrides[get_claim_queries_dep] = lambda: object()
    app.dependency_overrides[get_reviews_store] = lambda: object()

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing the required field entirely
            response = await client.patch(
                f"/api/v1/claims/{_KNOWN_CLAIM_ID}/resumen",
                json={},
            )

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_patch_resumen_empty_string_returns_422() -> None:
    """Empty string for resumen_editado must fail min_length=1 validation → 422."""
    import httpx

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    from app.api.deps import _get_optional_session as _dep_sess
    from app.api.v1.claims import _get_optional_session as _route_sess

    async def _real_session_stub() -> AsyncIterator[AsyncSession | None]:
        yield object()  # type: ignore[misc]

    app.dependency_overrides[_dep_sess] = _real_session_stub
    app.dependency_overrides[_route_sess] = _real_session_stub
    app.dependency_overrides[get_claim_queries_dep] = lambda: object()
    app.dependency_overrides[get_reviews_store] = lambda: object()

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/claims/{_KNOWN_CLAIM_ID}/resumen",
                json={"resumen_editado": ""},
            )

    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# GET /claims/import/template?format=json  (B4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_template_json_format_returns_array() -> None:
    """GET /claims/import/template?format=json returns a JSON array with expected keys."""
    import httpx

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/claims/import/template?format=json")

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list), "Expected a JSON array"
    assert len(body) >= 1

    skeleton = body[0]
    required_keys = {
        "id", "ramo", "cobertura", "asegurado_id", "poliza",
        "ciudad", "fecha_ocurrencia", "fecha_reporte",
        "monto_reclamado", "suma_asegurada", "estado", "sucursal",
        "descripcion",
    }
    missing = required_keys - set(skeleton.keys())
    assert not missing, f"Skeleton is missing keys: {missing}"


@pytest.mark.asyncio
async def test_import_template_default_returns_csv() -> None:
    """GET /claims/import/template (no format param) still returns CSV or 404 if file absent."""
    import httpx

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/claims/import/template")

    # Either CSV is served (200 with text/csv) or template file is missing (404).
    # Both are valid depending on whether data/samples/claims.sample.csv exists.
    assert response.status_code in (200, 404), response.text
    if response.status_code == 200:
        assert "text/csv" in response.headers.get("content-type", "")
