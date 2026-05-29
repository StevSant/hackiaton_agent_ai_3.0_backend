"""InMemoryFakeOcr — scripted OCR for unit tests (no network)."""

from __future__ import annotations


class InMemoryFakeOcr:
    """Returns a fixed text blob regardless of input. Satisfies OcrProvider."""

    def __init__(self, *, text: str) -> None:
        self._text = text

    async def extract_text(self, content: bytes, *, mime: str) -> str:
        return self._text
