"""OpenAI vision adapter for `OcrProvider` — OCR for scanned/image documents (A1).

OpenAI has no dedicated OCR endpoint; OCR is done by handing the document to a
vision-capable chat model and asking it to transcribe the text verbatim. Images
go in as an ``image_url`` data-URI part; PDFs go in as a ``file`` / ``file_data``
part (the model renders each page and reads it).

`import openai` stays confined to infrastructure adapters — feature code goes
through the `OcrProvider` port. Same convention as the embeddings + speech
adapters (root CLAUDE.md §11; the rule targets domain/use_cases/api/agents).
"""

from __future__ import annotations

import base64
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.errors import ProviderError

# Short transcription instruction; the document itself is the payload.
_TRANSCRIBE_PROMPT = (
    "Transcribe TODO el texto visible de este documento, en orden de lectura. "
    "Devuelve solo el texto plano, sin comentarios ni descripciones. "
    "Conserva saltos de línea y números tal como aparecen."
)


class OpenAIOcrAdapter:
    """`OcrProvider` impl backed by an OpenAI vision model."""

    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def extract_text(self, content: bytes, *, mime: str) -> str:
        b64 = base64.b64encode(content).decode("ascii")
        kwargs: dict[str, object] = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _TRANSCRIBE_PROMPT},
                        self._document_part(b64, mime),
                    ],
                }
            ],
        }
        try:
            completion = await self._client.chat.completions.create(**kwargs)  # type: ignore[call-overload]
        except Exception as exc:  # SDK/network/auth failures → typed provider error
            raise ProviderError(f"OpenAI OCR request failed: {exc}") from exc

        return (completion.choices[0].message.content or "").strip()

    @staticmethod
    def _document_part(b64: str, mime: str) -> dict[str, Any]:
        data_uri = f"data:{mime};base64,{b64}"
        if mime == "application/pdf":
            return {
                "type": "file",
                "file": {"filename": "document.pdf", "file_data": data_uri},
            }
        # Default to the vision image path for image/* (and anything else).
        return {"type": "image_url", "image_url": {"url": data_uri}}


def build_openai_ocr_adapter() -> OpenAIOcrAdapter:
    if settings.OPENAI_API_KEY is None:
        raise ProviderError("OPENAI_API_KEY is not set; cannot build OpenAIOcrAdapter")
    return OpenAIOcrAdapter(
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        model=settings.OCR_MODEL,
    )
