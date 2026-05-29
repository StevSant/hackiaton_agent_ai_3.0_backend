"""Tests for POST /api/v1/agent/document/docx — markdown → docx download."""

from __future__ import annotations

import base64
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


# Minimal valid 1x1 PNG (8-bit RGBA), base64-encoded.
_PNG_1X1_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4"
    "nGNgYGAAAAAEAAEnNCcKAAAAAElFTkSuQmCC"
)


async def _post_docx(body: dict) -> httpx.Response:
    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/v1/agent/document/docx", json=body)


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


@pytest.mark.asyncio
async def test_docx_embeds_chart_image_when_provided() -> None:
    """A valid PNG chart is embedded → 200 docx, larger than without the image."""
    markdown = "## Resumen\n\nCasos analizados.\n"
    base_body = {"titulo": "Informe con grafico", "contenido_markdown": markdown}

    response_no_image = await _post_docx(base_body)
    response_with_image = await _post_docx(
        {**base_body, "chart_image_base64": f"data:image/png;base64,{_PNG_1X1_BASE64}"}
    )

    assert response_no_image.status_code == 200, response_no_image.text
    assert response_with_image.status_code == 200, response_with_image.text
    assert _DOCX_CONTENT_TYPE in response_with_image.headers.get("content-type", "")
    assert response_with_image.content[:2] == b"PK"
    # Embedding the image makes the docx archive strictly larger.
    assert len(response_with_image.content) > len(response_no_image.content)


@pytest.mark.asyncio
async def test_docx_skips_malformed_chart_image_without_500() -> None:
    """A malformed chart_image_base64 is skipped silently — still returns 200."""
    response = await _post_docx(
        {
            "titulo": "Informe grafico roto",
            "contenido_markdown": "## Resumen\n\nContenido.\n",
            "chart_image_base64": "not%%%valid base64!!!",
        }
    )

    assert response.status_code == 200, response.text
    assert _DOCX_CONTENT_TYPE in response.headers.get("content-type", "")
    assert response.content[:2] == b"PK"


@pytest.mark.asyncio
async def test_docx_skips_non_png_base64_without_500() -> None:
    """Valid base64 that is not a PNG is skipped silently — still returns 200."""
    not_png = base64.b64encode(b"this is plain text, not a png").decode("ascii")
    response = await _post_docx(
        {
            "titulo": "Informe no png",
            "contenido_markdown": "## Resumen\n\nContenido.\n",
            "chart_image_base64": not_png,
        }
    )

    assert response.status_code == 200, response.text
    assert response.content[:2] == b"PK"
