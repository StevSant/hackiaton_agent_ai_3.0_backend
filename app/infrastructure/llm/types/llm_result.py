from pydantic import BaseModel

from app.infrastructure.llm.types.message import Message


class LLMResult(BaseModel):
    message: Message
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
