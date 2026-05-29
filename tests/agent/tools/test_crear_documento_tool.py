"""Tests for the `crear_documento` tool."""

from __future__ import annotations

import pytest

from app.agents.claims_agent.tools.crear_documento_tool import (
    CrearDocumentoInput,
    CrearDocumentoTool,
)


@pytest.mark.asyncio
async def test_crear_documento_echoes_titulo_and_contenido() -> None:
    """Tool returns the same titulo and contenido_markdown it received."""
    tool = CrearDocumentoTool()
    args = CrearDocumentoInput(
        titulo="Informe de casos críticos",
        contenido_markdown=(
            "## Casos en rojo\n\n"
            "| Siniestro | Score |\n"
            "|---|---|\n"
            "| **SIN-0001** | 85 |\n\n"
            "- Regla FS-07 activada.\n"
        ),
    )
    result = await tool.run(args)

    assert result.titulo == args.titulo
    assert result.contenido_markdown == args.contenido_markdown


@pytest.mark.asyncio
async def test_crear_documento_input_rejects_empty_titulo() -> None:
    """CrearDocumentoInput raises ValidationError when titulo is empty."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CrearDocumentoInput(titulo="", contenido_markdown="# Test")


@pytest.mark.asyncio
async def test_crear_documento_input_rejects_empty_contenido() -> None:
    """CrearDocumentoInput raises ValidationError when contenido_markdown is empty."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CrearDocumentoInput(titulo="Test", contenido_markdown="")
