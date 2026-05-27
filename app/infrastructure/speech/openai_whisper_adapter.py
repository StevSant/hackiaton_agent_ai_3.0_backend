"""OpenAI Whisper adapter for `SpeechTranscriber`.

`import openai` stays confined to infrastructure — feature code goes through the port.
"""

from io import BytesIO

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.errors import ProviderError


class OpenAIWhisperAdapter:
    """`SpeechTranscriber` impl backed by OpenAI's audio transcriptions API."""

    def __init__(self, api_key: str, model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def transcribe(
        self,
        *,
        audio: bytes,
        filename: str,
        content_type: str,
        language: str | None = None,
    ) -> str:
        del content_type  # OpenAI infers format from filename/extension.
        try:
            response = await self._client.audio.transcriptions.create(
                model=self._model,
                file=(filename, BytesIO(audio)),
                language=language,
            )
        except Exception as exc:
            raise ProviderError(f"Whisper transcription failed: {exc}") from exc

        text = response.text.strip()
        if not text:
            raise ProviderError("Whisper returned an empty transcription.")
        return text


def build_openai_whisper_adapter() -> OpenAIWhisperAdapter:
    if settings.OPENAI_API_KEY is None:
        raise ProviderError("OPENAI_API_KEY is not set; cannot build OpenAIWhisperAdapter")
    return OpenAIWhisperAdapter(
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        model=settings.WHISPER_MODEL,
    )
