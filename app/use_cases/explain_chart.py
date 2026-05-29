"""Explain a single insights chart using the LLM (one-shot, structured).

The caller (Angular city-insights dashboard) sends a plain-text `resumen` already
built from the chart's real numbers, plus the chart kind/title and city. This use
case builds a prompt, calls `LLMProvider.complete()` with structured output
`{explicacion_markdown}`, and returns it. It does NOT go through the ReAct claims
agent — same shape as `improve_document`, avoiding the /ask query loop.

Prompt file: app/agents/claims_agent/prompts/explain_grafico.v1.md
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


class ChartExplanation(BaseModel):
    explicacion_markdown: str = Field(
        ..., description="Explicación del gráfico en Markdown"
    )


def _build_user_payload(
    ciudad: str,
    chart_kind: str,
    chart_title: str,
    resumen: str,
) -> str:
    return (
        f"## Gráfico a explicar\n"
        f"**Ciudad:** {ciudad}\n"
        f"**Tipo de gráfico:** {chart_kind}\n"
        f"**Título:** {chart_title}\n\n"
        f"## Datos del gráfico (cifras reales)\n{resumen}\n\n"
        "Explica este gráfico para un analista, usando solo estas cifras.\n"
        'Responde ÚNICAMENTE con el objeto JSON: {"explicacion_markdown": "<explicación>"}'
    )


async def explain_chart(
    *,
    ciudad: str,
    chart_kind: str,
    chart_title: str,
    resumen: str,
    llm: LLMProvider,
    llm_model: str,
) -> ChartExplanation:
    """Call the LLM to explain one insights chart and return the explanation.

    Args:
        ciudad: City the chart belongs to.
        chart_kind: Chart family (stacked_area, scatter, gauge, rose, polar, radar, savings).
        chart_title: Human title shown on the card.
        resumen: Plain-text summary of the chart's real numbers (built client-side).
        llm: LLMProvider instance from DI.
        llm_model: Model identifier from settings.

    Returns:
        ChartExplanation with the Markdown explanation.

    Raises:
        ValueError: If the LLM response cannot be parsed.
    """
    system_prompt = _prompt_loader.load("explain_grafico", "v1")
    user_payload = _build_user_payload(ciudad, chart_kind, chart_title, resumen)

    response_format = ResponseFormat(
        schema_name="ChartExplanation",
        json_schema=ChartExplanation.model_json_schema(),
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
        raise ValueError(f"LLM returned invalid JSON for explain_chart: {exc}") from exc

    return ChartExplanation.model_validate(raw)
