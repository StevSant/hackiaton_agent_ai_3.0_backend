"""Shared LLM extraction pipeline for unstructured claim documents.

Both `_pdf_extractor.py` and `_docx_extractor.py` call `extract_claim_from_text`
to run the common prompt-→-structured-output-→-ClaimDetail pipeline.

Validation rules:
- Dates must be ISO YYYY-MM-DD parseable.
- `monto_reclamado >= 0`.
- `fecha_reporte >= fecha_ocurrencia`.
- Fields the LLM cannot reliably extract are omitted; Pydantic defaults fill them.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.infrastructure.llm.ports import LLMProvider
from app.infrastructure.llm.prompt_loader import PromptLoader
from app.infrastructure.llm.types import Message, ResponseFormat
from app.schemas.claim import ClaimDetail, ClaimReview, ReviewStatus
from app.schemas.risk import Tier

# PromptLoader is rooted at the prompts directory for the claims agent.
_PROMPTS_DIR = Path(__file__).parent.parent.parent / "agents" / "claims_agent" / "prompts"
_prompt_loader = PromptLoader(_PROMPTS_DIR)


# ---------------------------------------------------------------------------
# Slim extraction schema — only what a document would contain
# ---------------------------------------------------------------------------

class _ExtractedClaim(BaseModel):
    """Intermediate schema: what the LLM is asked to produce from the document.

    Optional fields default to None/empty; the upcast to ClaimDetail supplies
    safe defaults for the rest.
    """

    id: str | None = Field(default=None)
    cobertura: str = Field(default="Daños Materiales")
    asegurado: str = Field(default="Asegurado Desconocido")
    asegurado_id: str | None = Field(default=None)
    poliza: str | None = Field(default=None)
    ciudad: str = Field(default="Guayaquil")
    fecha_ocurrencia: str = Field(default="")
    fecha_reporte: str = Field(default="")
    monto_reclamado: float = Field(default=0.0)
    suma_asegurada: float = Field(default=0.0)
    descripcion: str = Field(default="")
    vehiculo_marca: str | None = Field(default=None)
    vehiculo_modelo: str | None = Field(default=None)
    vehiculo_anio: int | None = Field(default=None)
    vehiculo_placa: str | None = Field(default=None)
    vehiculo_chasis: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _parse_date_safe(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _ciudad_to_sucursal(ciudad: str) -> str:
    _MAP = {
        "Guayaquil": "Guayaquil Centro",
        "Quito": "Quito Norte",
    }
    return _MAP.get(ciudad, ciudad)


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

async def extract_claim_from_text(
    text: str,
    *,
    llm: LLMProvider,
    llm_model: str,
    source_hint: str = "documento",
) -> ClaimDetail:
    """Call the LLM with the document text and return a validated ClaimDetail.

    Args:
        text: Extracted plain text from the document.
        llm: LLMProvider instance (injected by the caller — never constructed here).
        llm_model: Model name to pass to the LLM (from settings).
        source_hint: Human-readable document type label for error messages.

    Returns:
        A ClaimDetail with extracted fields; omitted fields filled with safe defaults.

    Raises:
        ValueError: If the LLM response cannot be parsed or basic validation fails.
    """
    system_prompt = _prompt_loader.load("extract_claim_from_document", "v1")

    user_payload = (
        f"Analiza el siguiente {source_hint} y extrae los campos del siniestro:\n\n"
        f"---\n{text[:6000]}\n---\n\n"
        "Responde ÚNICAMENTE con el objeto JSON estructurado."
    )

    response_format = ResponseFormat(
        schema_name="ExtractedClaim",
        json_schema=_ExtractedClaim.model_json_schema(),
        strict=False,  # open-ended text fields; don't use strict mode
    )

    result = await llm.complete(
        messages=[
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_payload),
        ],
        model=llm_model,
        response_format=response_format,
    )

    # Parse the JSON the LLM returned
    try:
        raw: Any = json.loads(result.message.content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"LLM did not return valid JSON from {source_hint}: {exc}"
        ) from exc

    extracted = _ExtractedClaim.model_validate(raw)

    # --- Date validation ---
    fecha_ocurrencia = _parse_date_safe(extracted.fecha_ocurrencia)
    fecha_reporte = _parse_date_safe(extracted.fecha_reporte)

    if fecha_ocurrencia is None:
        raise ValueError(
            f"No se pudo extraer fecha_ocurrencia del {source_hint}. "
            "El documento puede no contener información suficiente."
        )
    if fecha_reporte is None:
        fecha_reporte = fecha_ocurrencia  # safe fallback
    if fecha_reporte < fecha_ocurrencia:
        fecha_reporte = fecha_ocurrencia  # fix invalid ordering

    # --- Amount validation ---
    monto = max(0.0, extracted.monto_reclamado)
    suma = max(0.0, extracted.suma_asegurada)

    # --- Vehicle (optional) ---
    from app.schemas.claim import ClaimVehicle  # local import avoids circular at module level
    vehiculo = None
    if extracted.vehiculo_marca and extracted.vehiculo_modelo:
        vehiculo = ClaimVehicle(
            marca=extracted.vehiculo_marca,
            modelo=extracted.vehiculo_modelo,
            anio=extracted.vehiculo_anio or 2020,
            placa=extracted.vehiculo_placa or "SIN-PLACA",
            chasis=extracted.vehiculo_chasis,
        )

    ciudad = extracted.ciudad or "Guayaquil"
    claim_id = extracted.id or f"DOC-{date.today().isoformat().replace('-', '')}-XXX"

    return ClaimDetail(
        id=claim_id,
        ramo="Vehículos",
        cobertura=extracted.cobertura or "Daños Materiales",
        asegurado=extracted.asegurado or "Asegurado Desconocido",
        asegurado_id=extracted.asegurado_id or f"ASG-DOC-{claim_id[-4:].upper()}",
        poliza=extracted.poliza or f"POL-DOC-{claim_id[-4:].upper()}",
        ciudad=ciudad,
        fecha_ocurrencia=fecha_ocurrencia,
        fecha_reporte=fecha_reporte,
        monto_reclamado=monto,
        suma_asegurada=suma,
        estado="Reserva",
        sucursal=_ciudad_to_sucursal(ciudad),
        vehiculo=vehiculo,
        descripcion=extracted.descripcion or "",
        score=0,
        nivel=Tier.verde,
        review=ClaimReview(status=ReviewStatus.pendiente),
    )
