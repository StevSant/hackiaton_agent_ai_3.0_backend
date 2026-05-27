from typing import Protocol


class SpeechTranscriber(Protocol):
    async def transcribe(
        self,
        *,
        audio: bytes,
        filename: str,
        content_type: str,
        language: str | None = None,
    ) -> str: ...
