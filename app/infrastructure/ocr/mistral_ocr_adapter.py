"""MistralOcrAdapter — OCR via Mistral's /v1/ocr endpoint (A1).

Provider SDK import is local to this file (the only place `mistralai` is
imported), mirroring the `infrastructure/llm` adapter convention. The Mistral
SDK call is synchronous, so it is pushed to a thread to keep the event loop
free (backend CLAUDE.md §2: no blocking I/O on the loop).

Mistral OCR returns one markdown blob per page; we join them. A data-URI is
used to pass the raw bytes inline (no upload round-trip).

SDK note (mistralai==2.4.8): the top-level `mistralai` namespace is a package
namespace with no direct exports. The client lives at
`mistralai.client.sdk.Mistral`; `DocumentURLChunk` at
`mistralai.client.models.DocumentURLChunk`.
"""

from __future__ import annotations

import asyncio
import base64

from app.core.errors import ProviderError


class MistralOcrAdapter:
    """`OcrProvider` impl backed by Mistral OCR."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def extract_text(self, content: bytes, *, mime: str) -> str:
        return await asyncio.to_thread(self._extract_sync, content, mime)

    def _extract_sync(self, content: bytes, mime: str) -> str:
        from mistralai.client.models import DocumentURLChunk  # local — only place mistralai used
        from mistralai.client.sdk import Mistral

        b64 = base64.b64encode(content).decode("ascii")
        data_uri = f"data:{mime};base64,{b64}"
        try:
            with Mistral(api_key=self._api_key) as client:
                response = client.ocr.process(
                    model=self._model,
                    document=DocumentURLChunk(document_url=data_uri),
                )
        except Exception as exc:  # SDK/network/auth failures → typed provider error
            raise ProviderError(f"Mistral OCR request failed: {exc}") from exc

        pages = getattr(response, "pages", None) or []
        text = "\n\n".join(getattr(page, "markdown", "") or "" for page in pages)
        return text.strip()
