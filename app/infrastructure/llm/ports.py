from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from app.infrastructure.llm.types import (
    LLMEvent,
    LLMResult,
    Message,
    ResponseFormat,
    ToolSpec,
)


@runtime_checkable
class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[ToolSpec] | None = None,
        response_format: ResponseFormat | None = None,
    ) -> LLMResult: ...

    def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[LLMEvent]: ...
