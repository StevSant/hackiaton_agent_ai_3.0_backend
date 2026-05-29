"""Tests for POST /api/v1/agent/document/docx — markdown → docx download."""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.api.deps import get_current_user
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.main import create_app

_DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def _stub_user() -> User:
    return User(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "analista@test.local"),
        email="analista@test.local",
        role=Role.analista,
        full_name="Test Analista",
    )


@pytest.mark.asyncio
async def test_docx_endpoint_returns_200_and_correct_content_type() -> None:
    """POST /agent/document/docx returns 200, docx content-type, non-empty bytes."""
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user

    body = {
        "titulo": "Informe de prueba",
        "contenido_markdown": (
            "## Resumen\n\n"
            "Casos analizados esta semana.\n\n"
            "| Siniestro | Score | Nivel |\n"
            "|---|---|---|\n"
            "| **SIN-0001** | 85 | Rojo |\n"
            "| SIN-0002 | 45 | Amarillo |\n\n"
            "- Regla FS-07 activada en dos casos.\n"
            "- Se recomienda revisión de campo.\n"
        ),
    }

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/agent/document/docx", json=body)

    assert response.status_code == 200, response.text
    assert _DOCX_CONTENT_TYPE in response.headers.get("content-type", "")
    assert len(response.content) > 0
    # Docx files begin with PK (zip local file header magic)
    assert response.content[:2] == b"PK"
    # Filename slug derived from titulo
    content_disp = response.headers.get("content-disposition", "")
    assert "informe-de-prueba.docx" in content_disp


@pytest.mark.asyncio
async def test_docx_endpoint_requires_auth() -> None:
    """POST /agent/document/docx returns 401 when no token is provided (AUTH_ENABLED)."""
    from app.core.config import settings

    if not settings.AUTH_ENABLED:
        pytest.skip("AUTH_ENABLED=false — auth gate not active")

    app = create_app()
    # No override — let real auth run

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/agent/document/docx",
                json={"titulo": "Test", "contenido_markdown": "# Hello"},
            )

    assert response.status_code in (401, 403), response.text
