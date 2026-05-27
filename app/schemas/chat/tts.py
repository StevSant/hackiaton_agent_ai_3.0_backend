from typing import Literal

from pydantic import BaseModel, Field

TtsVoice = Literal["alloy", "echo", "fable", "nova", "onyx", "shimmer"]


class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to synthesize — max 5 000 chars.")
    voice: TtsVoice | None = Field(
        None,
        description="OpenAI voice name. Defaults to settings.TTS_VOICE when omitted.",
    )
