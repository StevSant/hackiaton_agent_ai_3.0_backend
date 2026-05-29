"""OpenAI adapter for `LLMProvider` — sole provider for the hackathon (locked 2026-05-26).

The Anthropic SDK is intentionally NOT in pyproject. Post-hackathon, swapping providers
is a single new adapter file behind the same `LLMProvider` port.

`import openai` MUST stay confined to this module (root CLAUDE.md §11 — provider-agnostic
AI). Feature code goes through `get_llm()` → `LLMProvider`.
"""

import copy
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.errors import ProviderError
from app.infrastructure.llm.ports import LLMProvider
from app.infrastructure.llm.types import (
    LLMEvent,
    LLMResult,
    Message,
    ResponseFormat,
    ToolSpec,
)

# Keys OpenAI's strict structured-output mode rejects or ignores. Stripped from
# every schema node before the request; pydantic still enforces them on parse.
_STRIP_KEYS = (
    "default",
    "title",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "pattern",
    "format",
    "minItems",
    "maxItems",
)


def _normalize_strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Patch a pydantic JSON schema for OpenAI structured outputs in strict mode.

    OpenAI's strict mode requires every object node to declare
    `additionalProperties: false`, list ALL properties in `required`, and omit
    `default` keys. This walker enforces those rules on a deep copy so the
    caller's schema isn't mutated.
    """
    patched = copy.deepcopy(schema)
    _walk_strict(patched)
    return patched


def _walk_strict(node: Any) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_strict(item)
        return
    if not isinstance(node, dict):
        return

    for key in _STRIP_KEYS:
        node.pop(key, None)

    if node.get("type") == "object" or "properties" in node:
        node["additionalProperties"] = False
        props = node.get("properties")
        if isinstance(props, dict):
            node["required"] = list(props.keys())
            for prop_schema in props.values():
                _walk_strict(prop_schema)

    for key in ("items", "$defs", "definitions", "anyOf", "allOf", "oneOf"):
        if key in node:
            _walk_strict(node[key])


class OpenAIAdapter(LLMProvider):
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
            schema = (
                _normalize_strict_schema(response_format.json_schema)
                if response_format.strict
                else response_format.json_schema
            )
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": response_format.schema_name,
                    "schema": schema,
                    "strict": response_format.strict,
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


    async def synthesize_speech(self, text: str, voice: str) -> bytes:
        """Call OpenAI TTS and return raw MP3 bytes.

        Model is read from settings.TTS_MODEL (default gpt-4o-mini-tts).
        If that model is unavailable at runtime, change TTS_MODEL to "tts-1"
        in the environment — no code change needed.
        """
        try:
            response = await self._client.audio.speech.create(
                model=settings.TTS_MODEL,
                voice=voice,  # type: ignore[arg-type]  # openai SDK uses a Literal; voice is validated upstream
                input=text,
                response_format="mp3",
            )
            return response.content
        except Exception as exc:
            raise ProviderError(f"OpenAI TTS failed: {exc}") from exc


def build_openai_adapter() -> OpenAIAdapter:
    if settings.OPENAI_API_KEY is None:
        raise ProviderError("OPENAI_API_KEY is not set; cannot build OpenAIAdapter")
    return OpenAIAdapter(
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        default_model=settings.LLM_DEFAULT_MODEL,
    )
