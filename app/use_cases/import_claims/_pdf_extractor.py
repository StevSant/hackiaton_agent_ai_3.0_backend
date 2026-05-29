"""PDF parser with LLM extraction for claim import.

Uses `pdfplumber` to extract plain text from a PDF, then delegates to the
shared `extract_claim_from_text` pipeline which calls the LLM with a
structured output schema.

When the PDF has no extractable text (image-only scan) and an *ocr* provider
is supplied, the raw bytes are routed through OCR and the recovered text
feeds the same LLM extraction. With no OCR provider the historical
"image-only" ValueError is raised (pdfplumber-only path).

Raises:
    ValueError: If the PDF has no extractable text (image-only or blank) and
        no OCR provider is set, or if OCR also fails to recover enough text.
    ValueError: If the LLM cannot extract a valid ClaimDetail from the text.
"""

from __future__ import annotations

import asyncio
import io

from app.core.config import settings
from app.infrastructure.llm.ports import LLMProvider
from app.infrastructure.ocr import OcrProvider
from app.schemas.claim import ClaimDetail
from app.use_cases.import_claims._document_extractor import extract_claim_from_text

_MIN_TEXT_LENGTH = 100


def _extract_text_from_pdf(content: bytes) -> str:
    """Extract all text from a PDF using pdfplumber (blocking — run in thread)."""
    import pdfplumber  # local import keeps module-level imports clean; pdfplumber is optional

    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


async def parse_pdf(
    content: bytes,
    *,
    llm: LLMProvider,
    ocr: OcrProvider | None = None,
) -> list[ClaimDetail]:
    """Extract claim records from a PDF using pdfplumber + LLM structured output.

    Expected document types: synthetic denuncia policial, informe pericial,
    boleta de siniestro. The LLM is prompted to extract one claim per
    document (the returned list has length 1).

    When the PDF has no extractable text (image-only scan) and an *ocr* provider
    is supplied, the raw bytes are routed through OCR and the recovered text
    feeds the same LLM extraction. With no OCR provider the historical
    "image-only" ValueError is raised (pdfplumber-only path).

    Args:
        content: Raw PDF bytes.
        llm: LLMProvider instance (injected by the caller).
        ocr: Optional OCR provider for image-only documents.

    Returns:
        A list with a single ClaimDetail extracted from the document.

    Raises:
        ValueError: If the PDF has no extractable text and no OCR provider is set.
        ValueError: If LLM extraction fails or produces invalid data.
    """
    # pdfplumber uses blocking I/O (zipfile + PDF parsing) — push to thread pool
    text = await asyncio.to_thread(_extract_text_from_pdf, content)

    if len(text.strip()) < _MIN_TEXT_LENGTH:
        if ocr is None:
            raise ValueError(
                "PDF aparece vacío o es solo imágenes — no se pudo extraer texto suficiente "
                f"(extraídos {len(text.strip())} caracteres; mínimo {_MIN_TEXT_LENGTH})."
            )
        text = await ocr.extract_text(content, mime="application/pdf")
        if len(text.strip()) < _MIN_TEXT_LENGTH:
            raise ValueError(
                "OCR no recuperó texto suficiente del documento "
                f"(extraídos {len(text.strip())} caracteres; mínimo {_MIN_TEXT_LENGTH})."
            )

    claim = await extract_claim_from_text(
        text,
        llm=llm,
        llm_model=settings.LLM_DEFAULT_MODEL,
        source_hint="denuncia/informe policial en PDF",
    )
    return [claim]
