"""In-memory canned `LLMProvider` for unit tests and offline demos.

Returns deterministic responses keyed by query substrings. Special-cases for the
ReAct loop:
  - Step 1 (empty scratchpad) → return the scripted ReActDecision (tool call).
  - Step 2+ (scratchpad already has observations) → auto-return
    `{"action": "finish"}`.

This lets a single scripted tool decision exercise a full loop iteration in tests
without needing step-aware scripts.

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
      - `list` — a queue: each match dequeues the next item (useful for multi-step
        ReAct tests where you want different decisions across iterations).

    `default_compose` is the template used when no script matches and the call
    is non-structured. Citations from the user message are interpolated into
    `{citations}`.
    """

    def __init__(
        self,
        *,
        script: dict[str, Any] | None = None,
        default_compose: str = "Aquí tienes el resumen solicitado. Casos relevantes: {citations}.",
    ) -> None:
        # Preserve lists as-is (queue semantics); other values stored as-is.
        self._script: dict[str, Any] = {
            k.lower(): list(v) if isinstance(v, list) else v
            for k, v in (script or {}).items()
        }
        self._default_compose = default_compose

    def add_response(self, query_substring: str, response: Any) -> None:
        self._script[query_substring.lower()] = response

    @staticmethod
    def _extract_citations(text: str) -> str:
        import re

        ids = sorted(set(re.findall(r"\bSIN-[A-Z0-9_-]+\b", text, flags=re.IGNORECASE)))
        return ", ".join(ids[:5])

    @staticmethod
    def _focus_query(user_msg: str) -> str:
        """Extract the analyst's question + UI context from the react payload.

        Skips the tool catalog and scratchpad sections to avoid matching against
        tool descriptions (e.g. "revisar primero" appears inside `query_claims`
        description; without scoping we'd false-positive). Includes both:
          - `## Pregunta del analista` (the actual question)
          - `## Contexto del UI` (focus_claim_id hint when present)
        """
        marker = "## Pregunta del analista\n"
        if marker not in user_msg:
            return user_msg
        after = user_msg.split(marker, 1)[1]
        # Capture: question section + optional UI context. Stop at the tool catalog.
        for terminator in ("## Herramientas disponibles", "## scratchpad"):
            idx = after.find(terminator)
            if idx != -1:
                after = after[:idx]
                break
        return after

    def _match(self, query: str, *, want_dict: bool) -> Any | None:
        q = self._focus_query(query).lower()
        for substring, value in self._script.items():
            if substring not in q:
                continue
            # Queue semantics: dequeue + return; once empty, fall through.
            if isinstance(value, list):
                while value:
                    item = value.pop(0)
                    if want_dict and isinstance(item, dict):
                        return item
                    if not want_dict and not isinstance(item, dict):
                        return item
                continue
            if want_dict and isinstance(value, dict):
                return value
            if not want_dict and not isinstance(value, dict):
                return value
        return None

    @staticmethod
    def _looks_like_react_call(user_msg: str) -> bool:
        return "scratchpad (pasos anteriores)" in user_msg

    @staticmethod
    def _is_react_followup(user_msg: str) -> bool:
        """Detect a ReAct step 2+ call: scratchpad already has scored entries."""
        return '"step":' in user_msg and "(vacío — primera iteración)" not in user_msg

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

        # Scripts beat auto-finish: if the test scripted a decision (e.g. a
        # queue for multi-step ReAct), honor it. Auto-finish only kicks in
        # when there's nothing scripted for this query.
        hit: Any = self._match(last_user, want_dict=want_dict)

        if hit is None and want_dict and self._looks_like_react_call(last_user):
            if self._is_react_followup(last_user):
                # No script + already past iteration 1 → finish gracefully so
                # tests that script a single tool decision exercise a full loop.
                hit = {
                    "thought": "ya tengo evidencia del paso anterior",
                    "action": "finish",
                    "reason": "scratchpad lleno",
                }
            else:
                # No script + iteration 1 → finish without tool use so the
                # graph doesn't loop forever on unconfigured queries.
                hit = {
                    "thought": "sin script — termino sin llamar herramientas",
                    "action": "finish",
                    "reason": "no hay script para esta consulta",
                }
        elif hit is None and want_dict:
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
        chunk_size = 16
        for i in range(0, len(text), chunk_size):
            yield LLMEvent(type="token", data={"delta": text[i : i + chunk_size]})
        yield LLMEvent(type="done", data={"finish_reason": "stop"})
