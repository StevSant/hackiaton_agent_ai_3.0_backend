"""OcrProvider port — OCR for scanned/image documents (A1).

The adapter (Mistral) lives behind this Protocol so the import path stays
provider-agnostic and tests use a fake. Signature is the day-start contract
with Dev B's ingest wiring (spec B2).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class OcrProvider(Protocol):
    async def extract_text(self, content: bytes, *, mime: str) -> str:
        """Return plain text extracted from document *content* via OCR.

        Args:
            content: Raw document bytes (PDF or image).
            mime: The document's MIME type (e.g. "application/pdf", "image/png").
        """
        ...
