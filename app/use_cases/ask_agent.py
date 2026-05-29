"""Drive the claims-agent LangGraph and stream `ChatStreamEvent`s to the client.

Architecture:
  1. The graph (ReAct loop) populates `tool_results` + `citations` per turn.
     LangGraph's checkpointer persists `messages` across requests keyed by
     `thread_id == conversation_id` so follow-up questions see prior turns.
  2. `_compose_stream()` then calls `llm.stream()` with the compose prompts +
     tool results, yielding each token delta as a `TokenEvent` AS IT ARRIVES.
  3. After the stream finishes, we write the composed answer back into state
     as an `AIMessage` via `aupdate_state` so the next turn sees it.

This separation (graph for routing + tool dispatch, streaming compose outside
the graph) is intentional — compose is the only step that benefits from
token-by-token UX, and LangGraph nodes return state diffs, not streams.

Event sequence (golden path):
    agent_step(react_step) → tool_call / tool_result → ... → agent_step(compose)
      → token(delta)* → done(message_id)
On any unhandled exception → error(code, message) → done.
"""

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.claims_agent import ClaimsAgentDeps, build_graph
from app.core.config import settings
from app.domain.auth.user import User
from app.infrastructure.llm.types import Message
from app.schemas.agent import AgentAskRequest
from app.schemas.chat.stream import (
    AgentStepData,
    AgentStepEvent,
    ChartEvent,
    DocumentEvent,
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
from app.use_cases._chart_from_tools import maybe_build_chart
from app.use_cases._document_from_tools import maybe_build_document
from app.use_cases.conversations.conversation_persister import ConversationPersister

logger = logging.getLogger(__name__)


def _coerce_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except (ValueError, TypeError):
        return None


def _serialize_tool_results(results: list[dict]) -> str:
    # Minified JSON: ~10% fewer tokens to the compose LLM, lower TTFT.
    return json.dumps(results, ensure_ascii=False, separators=(",", ":"), default=str)


def _serialize_scratchpad(scratchpad: list[dict]) -> str:
    return json.dumps(scratchpad, ensure_ascii=False, separators=(",", ":"), default=str)


_CHART_HINT_TOOLS = ("aggregate_by_dimension", "query_claims")


def _has_chart_hint(tool_results: list[dict[str, Any]]) -> bool:
    """Cheap pre-check: does any collected tool result carry a chart_hint?

    Lets us emit a `chart_pending` SSE step BEFORE the compose stream so the
    UI can paint a chart skeleton in parallel with the streamed text instead
    of waiting for the final chart event.
    """
    for tr in tool_results:
        if tr.get("tool") not in _CHART_HINT_TOOLS:
            continue
        args = tr.get("args")
        if isinstance(args, dict) and isinstance(args.get("chart_hint"), dict):
            return True
    return False


class AskAgent:
    """Orchestrates one agent turn over SSE.

    The compiled graph + its checkpointer are pinned to this instance. Each
    `run()` call uses `conversation_id` as `thread_id`; LangGraph's checkpointer
    loads prior `messages` for that thread, the new HumanMessage gets reduced
    in, and the AIMessage gets written back after the compose stream.
    """

    def __init__(
        self,
        deps: ClaimsAgentDeps,
        persistence: ConversationPersister | None = None,
    ) -> None:
        self._deps = deps
        self._graph = build_graph(deps)
        self._persistence = persistence

    async def run(
        self,
        req: AgentAskRequest,
        *,
        user: User | None = None,
    ) -> AsyncIterator[
        TokenEvent
        | ToolCallEvent
        | ToolResultEvent
        | AgentStepEvent
        | ChartEvent
        | DocumentEvent
        | ErrorEvent
        | DoneEvent
    ]:
        thread_id = req.conversation_id or uuid.uuid4().hex
        config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
        # Each turn resets the per-turn channels but seeds a NEW HumanMessage
        # into the chat log (the trim_to_last_n_turns reducer appends + trims).
        initial_state: dict[str, Any] = {
            "query": req.query,
            "context": req.context.model_dump() if req.context else None,
            "tool_results": [],
            "citations": [],
            "step_count": 0,
            "scratchpad": [],
            "finished": False,
            "messages": [HumanMessage(content=req.query)],
        }
        message_id = uuid.uuid4().hex

        # --- Persist the user message before the stream starts (idempotent upsert).
        conversation_uuid = _coerce_uuid(thread_id)
        if self._persistence is not None and user is not None and conversation_uuid is not None:
            try:
                await self._persistence.before_stream(
                    conversation_id=conversation_uuid,
                    user=user,
                    query=req.query,
                    context_claim_id=(
                        req.context.focus_claim_id if req.context else None
                    ),
                    context_provider_id=(
                        req.context.focus_provider_id if req.context else None
                    ),
                    context_asegurado_id=(
                        req.context.focus_asegurado_id if req.context else None
                    ),
                )
            except Exception:
                logger.exception("Persisting user message failed; chat continues.")

        try:
            tool_results: list[dict[str, Any]] = []
            citations: list[str] = []
            scratchpad: list[dict[str, Any]] = []
            seen_tool_results = 0

            async for event in self._graph.astream_events(
                initial_state, config=config, version="v2"
            ):
                event_type = event.get("event", "")
                name = event.get("name", "")
                data = event.get("data", {})

                if event_type == "on_chain_end" and name == "react_step":
                    node_output = data.get("output") or {}
                    # Surface the LLM's reasoning thought from the scratchpad so the
                    # UI's transparency card shows WHAT the agent decided this step,
                    # not just "react_step ran". The latest entry is the one this
                    # iteration appended.
                    scratchpad_delta = node_output.get("scratchpad") or []
                    scratchpad.extend(scratchpad_delta)
                    latest = scratchpad_delta[-1] if scratchpad_delta else None
                    meta: dict[str, Any] | None = None
                    if isinstance(latest, dict) and latest.get("thought"):
                        meta = {"thought": latest["thought"], "step": latest.get("step")}
                    yield AgentStepEvent(data=AgentStepData(node=name, meta=meta))

                    new_results = node_output.get("tool_results") or []
                    for tool_result in new_results:
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
                    seen_tool_results += len(new_results)
                    new_citations = node_output.get("citations") or []
                    citations.extend(c for c in new_citations if c)

            # Emit a `chart_pending` step BEFORE compose so the UI can paint a
            # chart skeleton in parallel with the streamed answer text — instead
            # of waiting for the final `chart` event to learn one is coming.
            if _has_chart_hint(tool_results):
                yield AgentStepEvent(data=AgentStepData(node="chart_pending"))

            # Compose phase — streamed live from the LLM. Accumulate text so we
            # can persist it as an AIMessage for the next turn.
            yield AgentStepEvent(data=AgentStepData(node="compose"))
            answer_buffer: list[str] = []
            async for token in self._compose_stream(
                query=req.query,
                tool_results=tool_results,
                citations=citations,
                scratchpad=scratchpad,
                message_id=message_id,
            ):
                answer_buffer.append(token.data.delta)
                yield token

            # Persist the composed answer so the next turn (same thread_id)
            # sees it via the trim_to_last_n_turns reducer.
            full_answer = "".join(answer_buffer)
            if full_answer:
                await self._graph.aupdate_state(
                    config=config,
                    values={"messages": [AIMessage(content=full_answer)]},
                )

            # Build chart and document events BEFORE persistence so we can store
            # their payloads alongside the assistant message.
            chart_event = maybe_build_chart(tool_results, message_id)
            chart_payload_dict = (
                chart_event.data.model_dump(mode="json") if chart_event is not None else None
            )
            document_event = maybe_build_document(tool_results)
            document_payload_dict = (
                document_event.data.model_dump(mode="json")
                if document_event is not None
                else None
            )

            # Build transparency metadata from the accumulated stream events so
            # that GET /conversations/{id} can replay the explainability UI.
            # tool_calls list pairs each call with its result via call_id.
            tool_calls_for_meta: list[dict[str, Any]] = [
                {
                    "call_id": tr.get("call_id", ""),
                    "tool": tr.get("tool", "unknown"),
                    "args": tr.get("args", {}),
                    "result": tr.get("result"),
                }
                for tr in tool_results
            ]
            transparency: dict[str, Any] = {
                "steps": scratchpad,
                "tool_calls": tool_calls_for_meta,
                "citations": [{"claim_id": c} for c in citations if c],
            }
            # Embed document payload in transparency so it survives reload without
            # a new migration (reuses the existing JSONB column).
            if document_payload_dict is not None:
                transparency["document_payload"] = document_payload_dict

            # --- Persist the assistant message + chart payload + schedule title generation.
            if (
                self._persistence is not None
                and user is not None
                and conversation_uuid is not None
                and full_answer
            ):
                try:
                    assistant_seq = await self._persistence.after_stream(
                        conversation_id=conversation_uuid,
                        user=user,
                        answer=full_answer,
                        chart_payload=chart_payload_dict,
                        transparency_metadata=transparency,
                    )
                    self._persistence.schedule_title(
                        conversation_id=conversation_uuid,
                        user=user,
                        query=req.query,
                        answer=full_answer,
                        assistant_sequence=assistant_seq,
                    )
                except Exception:
                    logger.exception("Persisting assistant message failed; chat continues.")

            if chart_event is not None:
                yield chart_event
            if document_event is not None:
                yield document_event

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
        scratchpad: list[dict[str, Any]],
        message_id: str,
    ) -> AsyncIterator[TokenEvent]:
        """Stream the compose LLM call token-by-token."""
        system_prompt = self._deps.prompts.load("claims_system", "v4")
        compose_prompt = self._deps.prompts.load("compose", "v1")
        scratchpad_section = ""
        if scratchpad:
            scratchpad_section = (
                f"## scratchpad\n```json\n{_serialize_scratchpad(scratchpad)}\n```\n\n"
            )
        user_payload = (
            f"## Pregunta del analista\n{query}\n\n"
            f"{scratchpad_section}"
            f"## tool_results\n```json\n{_serialize_tool_results(tool_results)}\n```\n\n"
            f"## citations\n{', '.join(citations) if citations else '—'}\n\n"
            f"Componé la respuesta final siguiendo las reglas de `compose.v1`."
        )
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="system", content=compose_prompt),
            Message(role="user", content=user_payload),
        ]

        # Compose uses settings.COMPOSE_MODEL when set (e.g. gpt-4o for faster
        # TTFT on the demo machine), otherwise falls back to the deps default
        # (gpt-4o-mini). Keeping the override in env means cost is opt-in.
        compose_model = settings.COMPOSE_MODEL or self._deps.llm_model
        async for llm_event in self._deps.llm.stream(messages, model=compose_model):
            if llm_event.type == "token":
                delta = str(llm_event.data.get("delta", ""))
                if delta:
                    yield TokenEvent(data=TokenData(delta=delta, message_id=message_id))
            elif llm_event.type == "error":
                msg = str(llm_event.data.get("message", "LLM stream error"))
                error_delta = f"[Error componiendo respuesta: {msg}]"
                yield TokenEvent(data=TokenData(delta=error_delta, message_id=message_id))
                return
