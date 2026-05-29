"""parse_pdf routes image-only PDFs through OCR when a provider is supplied (A1)."""

from __future__ import annotations

import io

import pytest
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Spacer

from app.infrastructure.llm.fake_llm import InMemoryFakeLLM
from app.infrastructure.ocr import InMemoryFakeOcr
from app.use_cases.import_claims._pdf_extractor import parse_pdf


def _blank_pdf() -> bytes:
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=letter).build([Spacer(1, 1 * cm)])
    return buf.getvalue()


def _ocr_text() -> str:
    # Enough text (>100 chars) with the fields the extractor needs.
    return (
        "DENUNCIA POLICIAL. Robo total del vehículo Chevrolet Sail. "
        "Fecha de ocurrencia: 2026-03-10. Fecha de reporte: 2026-03-11. "
        "Monto reclamado: 12000. Suma asegurada: 20000. Ciudad: Guayaquil."
    )


@pytest.mark.asyncio
async def test_image_only_pdf_uses_ocr_when_provider_present() -> None:
    extracted = {
        "id": "SIN-OCR-001",
        "fecha_ocurrencia": "2026-03-10",
        "fecha_reporte": "2026-03-11",
        "monto_reclamado": 12000.0,
        "suma_asegurada": 20000.0,
        "descripcion": "Robo total del vehículo.",
    }
    llm = InMemoryFakeLLM(script={"analiza el siguiente": extracted})
    ocr = InMemoryFakeOcr(text=_ocr_text())

    claims = await parse_pdf(_blank_pdf(), llm=llm, ocr=ocr)

    assert len(claims) == 1
    assert claims[0].id == "SIN-OCR-001"


@pytest.mark.asyncio
async def test_image_only_pdf_without_ocr_still_raises() -> None:
    llm = InMemoryFakeLLM()
    with pytest.raises(ValueError, match="vacío|imágenes|texto suficiente"):
        await parse_pdf(_blank_pdf(), llm=llm, ocr=None)
