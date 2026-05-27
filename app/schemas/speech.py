from pydantic import BaseModel, Field


class TranscribeResponse(BaseModel):
    text: str = Field(description="Transcribed speech in plain text.")
