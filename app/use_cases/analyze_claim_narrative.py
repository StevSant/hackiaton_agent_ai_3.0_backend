"""analyze_claim_narrative — NLP read of a claim's free-text `descripcion`.

This is the NLP layer the rules engine always assumed but never had: it extracts
entities, judges narrative coherence (the genuine source for FS-09's
`narrativa_ilogica`), and writes a short summary. Pure use case — no DB I/O; the
caller decides whether/where to persist (see the on-demand cache-fill path).

Mirrors the structured-LLM pattern in ``improve_claim_resumen``.

Prompt file: app/agents/claims_agent/prompts/analyze_narrative.v1.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.infrastructure.llm.ports import LLMProvider
from app.infrastructure.llm.prompt_loader import PromptLoader
from app.infrastructure.llm.types import Message, ResponseFormat
from app.schemas.narrative_analysis import NarrativeAnalysis

_PROMPTS_DIR = Path(__file__).parent.parent / "agents" / "claims_agent" / "prompts"
_prompt_loader = PromptLoader(_PROMPTS_DIR)


async def analyze_claim_narrative(
    descripcion: str,
    *,
    llm: LLMProvider,
    llm_model: str,
) -> NarrativeAnalysis:
    """Run the NLP analyzer over a claim narrative and return the structured read.

    Args:
        descripcion: The claim's free-text narrative (`siniestros.descripcion`).
        llm:         LLMProvider instance from DI.
        llm_model:   Model identifier from settings.

    Returns:
        A populated ``NarrativeAnalysis``.

    Raises:
        ValueError: If the LLM response cannot be parsed.
    """
    system_prompt = _prompt_loader.load("analyze_narrative", "v1")
    user_payload = f"## Descripción del siniestro\n{descripcion}\n"

    response_format = ResponseFormat(
        schema_name="NarrativeAnalysis",
        json_schema=NarrativeAnalysis.model_json_schema(),
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
        raise ValueError(f"LLM returned invalid JSON for analyze_narrative: {exc}") from exc

    return NarrativeAnalysis.model_validate(raw)
