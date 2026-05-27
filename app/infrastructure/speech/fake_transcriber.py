"""Offline transcriber for tests and local dev without OpenAI."""


class InMemoryFakeTranscriber:
    """Returns a canned Spanish phrase so voice flows can be tested offline."""

    async def transcribe(
        self,
        *,
        audio: bytes,
        filename: str,
        content_type: str,
        language: str | None = None,
    ) -> str:
        del audio, filename, content_type, language
        return "¿Cuáles son los 5 siniestros con mayor riesgo?"
