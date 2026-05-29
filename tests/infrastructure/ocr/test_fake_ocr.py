"""InMemoryFakeOcr satisfies the OcrProvider port (used by parse_pdf tests)."""

from __future__ import annotations

import pytest

from app.infrastructure.ocr import InMemoryFakeOcr, OcrProvider


@pytest.mark.asyncio
async def test_fake_ocr_returns_scripted_text() -> None:
    fake: OcrProvider = InMemoryFakeOcr(text="DENUNCIA POLICIAL\nRobo total del vehículo.")
    out = await fake.extract_text(b"%PDF-1.4 fake bytes", mime="application/pdf")
    assert "Robo total" in out


@pytest.mark.asyncio
async def test_fake_ocr_is_runtime_checkable() -> None:
    fake = InMemoryFakeOcr(text="x")
    assert isinstance(fake, OcrProvider)
