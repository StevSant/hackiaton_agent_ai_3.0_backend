"""Word (.docx) parser with LLM extraction for claim import.

Uses `python-docx` to extract paragraph text from a .docx file, then
delegates to the shared `extract_claim_from_text` pipeline which calls
the LLM with a structured output schema.

Raises:
    ValueError: If the docx has no extractable text.
    ValueError: If the LLM cannot extract a valid ClaimDetail from the text.
"""

from __future__ import annotations

import asyncio
import io

from app.core.config import settings
from app.infrastructure.llm.ports import LLMProvider
from app.schemas.claim import ClaimDetail
from app.use_cases.import_claims._document_extractor import extract_claim_from_text

_MIN_TEXT_LENGTH = 100


def _extract_text_from_docx(content: bytes) -> str:
    """Extract paragraph text from a .docx file (blocking — run in thread)."""
    import docx  # local import keeps module-level imports clean; python-docx is optional

    doc = docx.Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


async def parse_docx(content: bytes, *, llm: LLMProvider) -> list[ClaimDetail]:
    """Extract claim records from a .docx file using python-docx + LLM structured output.

    Same shape as `parse_pdf` — one claim per document.

    Args:
        content: Raw .docx bytes.
        llm: LLMProvider instance (injected by the caller).

    Returns:
        A list with a single ClaimDetail extracted from the document.

    Raises:
        ValueError: If the docx has no extractable text (< 100 chars).
        ValueError: If LLM extraction fails or produces invalid data.
    """
    # python-docx uses blocking zip/XML parsing — push to thread pool
    text = await asyncio.to_thread(_extract_text_from_docx, content)

    if len(text.strip()) < _MIN_TEXT_LENGTH:
        raise ValueError(
            "Archivo Word aparece vacío — no se pudo extraer texto suficiente "
            f"(extraídos {len(text.strip())} caracteres; mínimo {_MIN_TEXT_LENGTH})."
        )

    claim = await extract_claim_from_text(
        text,
        llm=llm,
        llm_model=settings.LLM_DEFAULT_MODEL,
        source_hint="informe/denuncia en formato Word",
    )
    return [claim]
