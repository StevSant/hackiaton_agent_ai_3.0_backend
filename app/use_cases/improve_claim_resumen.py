"""Improve or regenerate the analyst summary of a claim using the LLM.

The caller decides whether to persist the result (via PATCH /resumen).
This use case only generates; it never writes to the DB.

Prompt file: app/agents/claims_agent/prompts/improve_resumen.v1.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.infrastructure.llm.ports import LLMProvider
from app.infrastructure.llm.prompt_loader import PromptLoader
from app.infrastructure.llm.types import Message, ResponseFormat
from app.schemas.claim import ClaimDetail

_PROMPTS_DIR = Path(__file__).parent.parent / "agents" / "claims_agent" / "prompts"
_prompt_loader = PromptLoader(_PROMPTS_DIR)


class _ImprovedResumen(BaseModel):
    resumen: str


def _build_user_payload(claim: ClaimDetail, instrucciones: str | None) -> str:
    """Compose the user message from claim data + optional instructions."""
    rules_fired = (
        "\n".join(
            f"- {a.code}: {a.detalle} ({a.puntos} pts, severidad {a.severidad})"
            for a in claim.alertas
        )
        or "Ninguna regla activada."
    )

    ml_line = (
        f"Probabilidad ML de posible fraude: {claim.ml_probability * 100:.1f}%"
        if claim.ml_probability is not None
        else "Modelo ML no disponible."
    )

    current_summary = claim.resumen_editado or "(sin resumen previo)"

    instruction_block = (
        f"\n## Instrucciones especiales del analista\n{instrucciones}\n"
        if instrucciones
        else "\nMejora el resumen de la mejor manera: más claro, bien estructurado, listo para el analista.\n"
    )

    return (
        f"## Datos del caso\n"
        f"- ID: {claim.id}\n"
        f"- Asegurado: {claim.asegurado} (ID: {claim.asegurado_id})\n"
        f"- Póliza: {claim.poliza} | Cobertura: {claim.cobertura} | Ramo: {claim.ramo}\n"
        f"- Ciudad: {claim.ciudad} | Sucursal: {claim.sucursal}\n"
        f"- Fecha ocurrencia: {claim.fecha_ocurrencia}\n"
        f"- Fecha reporte: {claim.fecha_reporte}\n"
        f"- Monto reclamado: ${claim.monto_reclamado:,.2f}\n"
        f"- Suma asegurada: ${claim.suma_asegurada:,.2f}\n"
        f"- Estado: {claim.estado}\n"
        f"- Score: {claim.score}/100 | Nivel: {claim.nivel.value}\n"
        f"- {ml_line}\n"
        f"\n## Reglas activadas\n{rules_fired}\n"
        f"\n## Descripción del siniestro\n{claim.descripcion}\n"
        f"\n## Resumen actual\n{current_summary}\n"
        f"{instruction_block}"
        "\nResponde ÚNICAMENTE con el objeto JSON: {\"resumen\": \"<texto>\"}"
    )


async def improve_claim_resumen(
    claim: ClaimDetail,
    *,
    llm: LLMProvider,
    llm_model: str,
    instrucciones: str | None = None,
) -> str:
    """Call the LLM to improve the claim summary and return the improved text.

    Args:
        claim: Full claim detail (score, alertas, descripcion, etc.).
        llm: LLMProvider instance from DI.
        llm_model: Model identifier from settings.
        instrucciones: Optional analyst instructions for the LLM.

    Returns:
        The improved summary string.

    Raises:
        ValueError: If the LLM response cannot be parsed.
    """
    system_prompt = _prompt_loader.load("improve_resumen", "v1")
    user_payload = _build_user_payload(claim, instrucciones)

    response_format = ResponseFormat(
        schema_name="ImprovedResumen",
        json_schema=_ImprovedResumen.model_json_schema(),
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
        raise ValueError(f"LLM returned invalid JSON for improve_resumen: {exc}") from exc

    parsed = _ImprovedResumen.model_validate(raw)
    return parsed.resumen
