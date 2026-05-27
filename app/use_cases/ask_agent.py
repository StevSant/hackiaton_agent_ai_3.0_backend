"""Drive the claims-agent LangGraph and stream `ChatStreamEvent`s to the client.

Translates LangGraph's internal event stream into our wire shape. Per backend
CLAUDE.md §7: frontend never sees raw LangGraph events.

Event sequence (golden path):
    agent_step(route)           → routing intent decided
    agent_step(<intent>)        → entering an intent node
    tool_call(<tool>)           → before the tool runs
    tool_result(<tool>)         → after the tool returns
    agent_step(compose)         → entering compose
    token(delta)*               → composed answer streamed in chunks
    done(message_id)            → end of stream
On any unhandled exception → error(code, message) → done.
"""

import uuid
from collections.abc import AsyncIterator

from app.agents.claims_agent import ClaimsAgentDeps, build_graph
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

_STREAM_CHUNK = 16  # characters per token event when re-chunking compose output


class AskAgent:
    """Orchestrates one agent turn over SSE.

    Stateless: a new graph instance per call. LangGraph caches its compilation
    internally, so this is cheap. Conversation state isn't needed for the 12-NL
    use case — each question is self-contained.
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
            final_state: dict[str, object] | None = None
            seen_tool_results = 0

            async for event in self._graph.astream_events(
                initial_state, version="v2"
            ):
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
                    "compose",
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

                if event_type == "on_chain_end" and name == "compose":
                    node_output = data.get("output") or {}
                    answer = str(node_output.get("answer") or "")
                    message_id = str(node_output.get("message_id") or message_id)
                    for chunk in _chunked(answer, _STREAM_CHUNK):
                        yield TokenEvent(data=TokenData(delta=chunk, message_id=message_id))
                    final_state = node_output

            if final_state is None:
                yield ErrorEvent(
                    data=ErrorData(code="empty_graph", message="Agent produced no compose output")
                )
            yield DoneEvent(data=DoneData(message_id=message_id))

        except Exception as exc:
            yield ErrorEvent(data=ErrorData(code="agent_error", message=str(exc)))
            yield DoneEvent(data=DoneData(message_id=message_id))


def _chunked(text: str, size: int) -> list[str]:
    if not text:
        return []
    return [text[i : i + size] for i in range(0, len(text), size)]
