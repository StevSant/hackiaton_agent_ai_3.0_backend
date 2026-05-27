"""OpenAI adapter for `LLMProvider` — sole provider for the hackathon (locked 2026-05-26).

The Anthropic SDK is intentionally NOT in pyproject. Post-hackathon, swapping providers
is a single new adapter file behind the same `LLMProvider` port.

`import openai` MUST stay confined to this module (root CLAUDE.md §11 — provider-agnostic
AI). Feature code goes through `get_llm()` → `LLMProvider`.
"""

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.errors import ProviderError
from app.infrastructure.llm.types import (
    LLMEvent,
    LLMResult,
    Message,
    ResponseFormat,
    ToolSpec,
)


class OpenAIAdapter:
    """`LLMProvider` impl backed by OpenAI's Chat Completions API."""

    def __init__(self, api_key: str, default_model: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
        self._default_model = default_model

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[ToolSpec] | None = None,
        response_format: ResponseFormat | None = None,
    ) -> LLMResult:
        kwargs: dict[str, object] = {
            "model": model or self._default_model,
            "messages": [m.model_dump() for m in messages],
        }
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]
        if response_format is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_format.schema_name,
                    "schema": response_format.json_schema,
                    "strict": True,
                },
            }

        try:
            completion = await self._client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
        except Exception as exc:
            raise ProviderError(f"OpenAI request failed: {exc}") from exc

        choice = completion.choices[0]
        usage = completion.usage
        return LLMResult(
            message=Message(role="assistant", content=choice.message.content or ""),
            finish_reason=choice.finish_reason,
            input_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            output_tokens=getattr(usage, "completion_tokens", None) if usage else None,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[LLMEvent]:
        kwargs: dict[str, object] = {
            "model": model or self._default_model,
            "messages": [m.model_dump() for m in messages],
            "stream": True,
        }
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]

        try:
            stream = await self._client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
            async for chunk in stream:  # type: ignore[union-attr]
                choice = chunk.choices[0] if chunk.choices else None
                if choice is None:
                    continue
                delta = choice.delta
                if delta.content:
                    yield LLMEvent(type="token", data={"delta": delta.content})
                if choice.finish_reason:
                    yield LLMEvent(type="done", data={"finish_reason": choice.finish_reason})
        except Exception as exc:
            yield LLMEvent(type="error", data={"code": "provider_error", "message": str(exc)})


def build_openai_adapter() -> OpenAIAdapter:
    if settings.OPENAI_API_KEY is None:
        raise ProviderError("OPENAI_API_KEY is not set; cannot build OpenAIAdapter")
    return OpenAIAdapter(
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        default_model=settings.LLM_DEFAULT_MODEL,
    )
