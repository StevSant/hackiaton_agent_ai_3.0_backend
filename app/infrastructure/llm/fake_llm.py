"""In-memory canned `LLMProvider` for unit tests and offline demos.

Returns deterministic responses keyed by `(intent_hint, query_substring)`. The
agent test suite uses this so unit tests never hit the network and never burn
real OpenAI credits. Real-LLM smoke tests live under `tests/integration/` and
are gated by `@pytest.mark.integration`.

Spec reference: V7.5 (12-NL-questions acceptance test).
"""

from collections.abc import AsyncIterator
from typing import Any

from app.infrastructure.llm.types import (
    LLMEvent,
    LLMResult,
    Message,
    ResponseFormat,
    ToolSpec,
)


class InMemoryFakeLLM:
    """`LLMProvider` impl driven by an in-memory script.

    `script` maps query substrings (case-insensitive) to either:
      - `str` — returned as `assistant` content for `complete()` / streamed in `stream()`.
      - `dict` — returned as a JSON-serializable structured output (for `response_format`).

    `default_compose` is the template used by the `compose` node when no script
    entry matches. Citations from `tool_results` are interpolated into `{citations}`.
    """

    def __init__(
        self,
        *,
        script: dict[str, Any] | None = None,
        default_compose: str = "Aquí tienes el resumen solicitado. Casos relevantes: {citations}.",
    ) -> None:
        self._script = {k.lower(): v for k, v in (script or {}).items()}
        self._default_compose = default_compose

    def add_response(self, query_substring: str, response: Any) -> None:
        self._script[query_substring.lower()] = response

    @staticmethod
    def _extract_citations(text: str) -> str:
        """Pull `SIN-XXXX` IDs out of the compose payload — used by the default template."""
        import re

        ids = sorted(set(re.findall(r"\bSIN-[A-Z0-9_-]+\b", text, flags=re.IGNORECASE)))
        return ", ".join(ids[:5])

    def _match(self, query: str, *, want_dict: bool) -> Any | None:
        q = query.lower()
        for substring, value in self._script.items():
            if substring not in q:
                continue
            if want_dict and isinstance(value, dict):
                return value
            if not want_dict and not isinstance(value, dict):
                return value
        return None

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[ToolSpec] | None = None,
        response_format: ResponseFormat | None = None,
    ) -> LLMResult:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        want_dict = response_format is not None
        hit = self._match(last_user, want_dict=want_dict)

        if hit is None and want_dict:
            # Defensive default for structured calls: return a minimal valid object
            # matching the IntentChoice schema (the agent only uses structured output
            # for routing today).
            hit = {"intent": "query_claims"}

        if hit is None:
            content = self._default_compose.format(
                citations=self._extract_citations(last_user) or "—"
            )
        elif isinstance(hit, dict):
            import json

            content = json.dumps(hit, ensure_ascii=False)
        else:
            content = str(hit)
        return LLMResult(
            message=Message(role="assistant", content=content),
            finish_reason="stop",
            input_tokens=0,
            output_tokens=len(content),
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[ToolSpec] | None = None,
    ) -> AsyncIterator[LLMEvent]:
        result = await self.complete(messages, model=model, tools=tools)
        text = result.message.content
        # stream in 16-char chunks so consumers can verify multi-event handling
        chunk_size = 16
        for i in range(0, len(text), chunk_size):
            yield LLMEvent(type="token", data={"delta": text[i : i + chunk_size]})
        yield LLMEvent(type="done", data={"finish_reason": "stop"})
