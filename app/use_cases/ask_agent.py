"""Drive the claims-agent LangGraph and stream `ChatStreamEvent`s to the client.

Architecture:
  1. The graph (route → intent → END) populates `tool_results` + `citations`.
  2. `_compose_stream()` then calls `llm.stream()` with the compose prompts +
     tool results, yielding each token delta as a `TokenEvent` AS IT ARRIVES.

This separation (graph for deterministic routing, streaming compose for generative
output) is intentional — per backend CLAUDE.md §7 the frontend never sees raw
LangGraph events, and compose is the only step that genuinely benefits from
token-by-token UX.

Event sequence (golden path):
    agent_step(route) → routing decided
    agent_step(<intent>) → entering intent node
    tool_call(<tool>) / tool_result(<tool>) → tool execution
    agent_step(compose) → entering compose stream
    token(delta)* → live token stream from the LLM
    done(message_id) → end of stream
On any unhandled exception → error(code, message) → done.
"""

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.agents.claims_agent import ClaimsAgentDeps, build_graph
from app.infrastructure.llm.types import Message
from app.schemas.agent import AgentAskRequest
from app.schemas.chat.stream import (
    AgentStepData,
    AgentStepEvent,
    DoneData,
    DoneEvent,
    ErrorData,
    ErrorEvent,
    TokenData,
    TokenEvent,
    ToolCallData,
    ToolCallEvent,
    ToolResultData,
    ToolResultEvent,
)


def _serialize_tool_results(results: list[dict]) -> str:
    return json.dumps(results, ensure_ascii=False, indent=2, default=str)


class AskAgent:
    """Orchestrates one agent turn over SSE.

    Stateless across requests: the compiled graph is pinned to this instance but
    each `run()` call gets fresh state. Conversation memory isn't needed for the
    12-NL use case — each question is self-contained.
    """

    def __init__(self, deps: ClaimsAgentDeps) -> None:
        self._deps = deps
        self._graph = build_graph(deps)

    async def run(
        self, req: AgentAskRequest
    ) -> AsyncIterator[
        TokenEvent | ToolCallEvent | ToolResultEvent | AgentStepEvent | ErrorEvent | DoneEvent
    ]:
        initial_state = {
            "query": req.query,
            "context": req.context.model_dump() if req.context else None,
            "tool_results": [],
            "citations": [],
        }
        message_id = uuid.uuid4().hex

        try:
            tool_results: list[dict[str, Any]] = []
            citations: list[str] = []
            seen_tool_results = 0

            async for event in self._graph.astream_events(initial_state, version="v2"):
                event_type = event.get("event", "")
                name = event.get("name", "")
                data = event.get("data", {})

                if event_type == "on_chain_start" and name in {
                    "route",
                    "query_claims",
                    "explain_case",
                    "aggregate",
                    "documents",
                    "summarize",
                }:
                    yield AgentStepEvent(data=AgentStepData(node=name))

                if event_type == "on_chain_end" and name in {
                    "query_claims",
                    "explain_case",
                    "aggregate",
                    "documents",
                    "summarize",
                }:
                    node_output = data.get("output") or {}
                    new_results = node_output.get("tool_results") or []
                    for tool_result in new_results[seen_tool_results:]:
                        tool_results.append(tool_result)
                        yield ToolCallEvent(
                            data=ToolCallData(
                                tool=tool_result.get("tool", "unknown"),
                                args=tool_result.get("args", {}),
                                call_id=tool_result.get("call_id", uuid.uuid4().hex),
                            )
                        )
                        yield ToolResultEvent(
                            data=ToolResultData(
                                call_id=tool_result.get("call_id", ""),
                                result=tool_result.get("result"),
                            )
                        )
                    seen_tool_results = len(new_results)
                    new_citations = node_output.get("citations") or []
                    citations.extend(c for c in new_citations if c)

            # Compose phase — streamed live from the LLM.
            yield AgentStepEvent(data=AgentStepData(node="compose"))
            async for token in self._compose_stream(
                query=req.query,
                tool_results=tool_results,
                citations=citations,
                message_id=message_id,
            ):
                yield token

            yield DoneEvent(data=DoneData(message_id=message_id))

        except Exception as exc:
            yield ErrorEvent(data=ErrorData(code="agent_error", message=str(exc)))
            yield DoneEvent(data=DoneData(message_id=message_id))

    async def _compose_stream(
        self,
        *,
        query: str,
        tool_results: list[dict[str, Any]],
        citations: list[str],
        message_id: str,
    ) -> AsyncIterator[TokenEvent]:
        """Stream the compose LLM call token-by-token.

        Uses the LLM's `stream()` method directly. If streaming fails for any
        reason (e.g. FakeLLM with no scripted entry), we fall back to a single
        token containing the full text — keeps the demo robust.
        """
        system_prompt = self._deps.prompts.load("claims_system", "v1")
        compose_prompt = self._deps.prompts.load("compose", "v1")
        user_payload = (
            f"## Pregunta del analista\n{query}\n\n"
            f"## tool_results\n```json\n{_serialize_tool_results(tool_results)}\n```\n\n"
            f"## citations\n{', '.join(citations) if citations else '—'}\n\n"
            f"Componé la respuesta final siguiendo las reglas de `compose.v1`."
        )
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="system", content=compose_prompt),
            Message(role="user", content=user_payload),
        ]

        async for llm_event in self._deps.llm.stream(messages, model=self._deps.llm_model):
            if llm_event.type == "token":
                delta = str(llm_event.data.get("delta", ""))
                if delta:
                    yield TokenEvent(data=TokenData(delta=delta, message_id=message_id))
            elif llm_event.type == "error":
                # Surface LLM-side errors as a single error token then bail.
                msg = str(llm_event.data.get("message", "LLM stream error"))
                error_delta = f"[Error componiendo respuesta: {msg}]"
                yield TokenEvent(
                    data=TokenData(delta=error_delta, message_id=message_id)
                )
                return
