"""Transcribe a short voice clip via the configured `SpeechTranscriber` port."""

from __future__ import annotations

import re

from app.core.config import settings
from app.core.errors import ValidationFailed
from app.infrastructure.speech.ports import SpeechTranscriber
from app.schemas.speech import TranscribeResponse


def _normalize_mime(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def _safe_filename(name: str) -> str:
    base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    return re.sub(r"[^\w.\-]", "_", base) or "audio.webm"


async def transcribe_audio(
    *,
    transcriber: SpeechTranscriber,
    data: bytes,
    filename: str,
    content_type: str,
    language: str | None = "es",
) -> TranscribeResponse:
    if not data:
        raise ValidationFailed("No se recibió audio para transcribir.")

    if len(data) > settings.TRANSCRIBE_MAX_BYTES:
        max_mb = settings.TRANSCRIBE_MAX_BYTES // (1024 * 1024)
        raise ValidationFailed(f"El audio excede el tamaño máximo permitido ({max_mb} MB).")

    normalized_mime = _normalize_mime(content_type)
    if normalized_mime not in settings.TRANSCRIBE_ALLOWED_MIME:
        allowed = ", ".join(settings.TRANSCRIBE_ALLOWED_MIME)
        raise ValidationFailed(
            f"Tipo de audio no permitido: {content_type!r}. Tipos aceptados: {allowed}."
        )

    text = await transcriber.transcribe(
        audio=data,
        filename=_safe_filename(filename),
        content_type=normalized_mime,
        language=language,
    )
    return TranscribeResponse(text=text)
