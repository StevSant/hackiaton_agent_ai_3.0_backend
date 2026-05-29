"""Improve or regenerate an agent-generated document using the LLM.

Callers provide the current titulo + contenido_markdown and optional analyst
instructions. The use case builds a prompt, calls `LLMProvider.complete()` with
structured output `{titulo, contenido_markdown}`, and returns the improved document.

Prompt file: app/agents/claims_agent/prompts/improve_documento.v1.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.infrastructure.llm.ports import LLMProvider
from app.infrastructure.llm.prompt_loader import PromptLoader
from app.infrastructure.llm.types import Message, ResponseFormat

_PROMPTS_DIR = Path(__file__).parent.parent / "agents" / "claims_agent" / "prompts"
_prompt_loader = PromptLoader(_PROMPTS_DIR)


class ImprovedDocument(BaseModel):
    titulo: str = Field(..., description="Título del documento mejorado")
    contenido_markdown: str = Field(..., description="Contenido mejorado en Markdown")


def _build_user_payload(
    titulo: str,
    contenido_markdown: str,
    instrucciones: str | None,
) -> str:
    instruction_block = (
        f"\n## Instrucciones especiales del analista\n{instrucciones}\n"
        if instrucciones
        else "\nMejora el documento de la mejor manera: más claro, mejor estructurado, con encabezados, tablas y viñetas donde corresponda.\n"
    )

    return (
        f"## Documento actual\n"
        f"**Título:** {titulo}\n\n"
        f"**Contenido:**\n\n{contenido_markdown}\n"
        f"{instruction_block}"
        '\nResponde ÚNICAMENTE con el objeto JSON: {"titulo": "<título>", "contenido_markdown": "<contenido>"}'
    )


async def improve_document(
    titulo: str,
    contenido_markdown: str,
    *,
    llm: LLMProvider,
    llm_model: str,
    instrucciones: str | None = None,
) -> ImprovedDocument:
    """Call the LLM to improve a document and return the improved version.

    Args:
        titulo: Current document title.
        contenido_markdown: Current document body in Markdown.
        llm: LLMProvider instance from DI.
        llm_model: Model identifier from settings.
        instrucciones: Optional analyst instructions for the LLM.

    Returns:
        ImprovedDocument with the new titulo and contenido_markdown.

    Raises:
        ValueError: If the LLM response cannot be parsed.
    """
    system_prompt = _prompt_loader.load("improve_documento", "v1")
    user_payload = _build_user_payload(titulo, contenido_markdown, instrucciones)

    response_format = ResponseFormat(
        schema_name="ImprovedDocument",
        json_schema=ImprovedDocument.model_json_schema(),
        strict=False,
    )

    result = await llm.complete(
        messages=[
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_payload),
        ],
        model=llm_model,
        response_format=response_format,
    )

    try:
        raw: Any = json.loads(result.message.content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM returned invalid JSON for improve_document: {exc}"
        ) from exc

    return ImprovedDocument.model_validate(raw)
