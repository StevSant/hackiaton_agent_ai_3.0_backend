"""One iteration of the ReAct loop.

The LLM:
  1. Sees the query, the tool catalog, and the scratchpad of prior steps.
  2. Outputs a `ReActDecision` (structured): thought + (use_tool|finish) + args.
  3. We dispatch the chosen tool, observe the result, and append a scratchpad
     entry. If the LLM picks `finish` (or we hit `max_react_steps`), we set
     `finished=True` so the graph conditional edge routes to END.

Failure-safe: malformed LLM output, unknown tool, or invalid args all push a
clear error observation onto the scratchpad and continue — the loop bound and
the compose stage handle the rest.
"""

import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import ValidationError

from app.agents.claims_agent._tool_dispatcher import FocusContext
from app.agents.claims_agent.dependencies import ClaimsAgentDeps
from app.agents.claims_agent.react import ReActDecision, ScratchpadEntry
from app.agents.claims_agent.state import ClaimsAgentState
from app.infrastructure.llm.types import Message, ResponseFormat


def _format_scratchpad(scratchpad: list[dict[str, Any]]) -> str:
    if not scratchpad:
        return "(vacío — primera iteración)"
    return json.dumps(scratchpad, ensure_ascii=False, indent=2, default=str)


def _format_history(messages: list[BaseMessage], *, current_query: str, limit: int = 6) -> str:
    """Render the last `limit` non-current messages as a short transcript.

    Drops the CURRENT turn's HumanMessage (it's already in the user payload via
    `## Pregunta del analista`) so we don't double-show it. Format keeps the
    LLM oriented — "Analista said X, you answered Y" — without dumping JSON.
    """
    if not messages:
        return "(sin historial — primera consulta)"
    # Drop the most recent HumanMessage if it matches the current query (the
    # one we just seeded for this turn).
    history: list[BaseMessage] = list(messages)
    if history and isinstance(history[-1], HumanMessage):
        last = history[-1]
        if isinstance(last.content, str) and last.content.strip() == current_query.strip():
            history = history[:-1]
    if not history:
        return "(sin historial — primera consulta)"
    tail = history[-limit:]
    rendered: list[str] = []
    for msg in tail:
        if isinstance(msg, HumanMessage):
            prefix = "Analista"
        elif isinstance(msg, AIMessage):
            prefix = "Asistente"
        else:
            prefix = msg.type.capitalize() if hasattr(msg, "type") else "Mensaje"
        text = msg.content if isinstance(msg.content, str) else json.dumps(msg.content, default=str)
        # Compact each turn — single line, truncate long answers.
        text = " ".join(text.split())
        if len(text) > 280:
            text = text[:277] + "..."
        rendered.append(f"- {prefix}: {text}")
    return "\n".join(rendered)


def _extract_citations(tool_name: str, result: Any) -> list[str]:
    """Best-effort citation harvest from a tool result.

    Different tools surface claim IDs in different fields; this normalizes.
    """
    if not isinstance(result, dict):
        return []
    citations: list[str] = []
    # query_claims: result.claims[].id
    for c in result.get("claims") or []:
        if isinstance(c, dict):
            cid = c.get("id") or c.get("claim_id")
            if isinstance(cid, str):
                citations.append(cid)
    # get_claim_detail: result.claim.id
    claim = result.get("claim")
    if isinstance(claim, dict) and isinstance(claim.get("id"), str):
        citations.append(claim["id"])
    # aggregate: result.rows[].example_claim_id
    for row in result.get("rows") or []:
        if isinstance(row, dict) and isinstance(row.get("example_claim_id"), str):
            citations.append(row["example_claim_id"])
    # summarize: result.summary.top_rojo[].id
    summary = result.get("summary")
    if isinstance(summary, dict):
        for c in summary.get("top_rojo") or []:
            if isinstance(c, dict) and isinstance(c.get("id"), str):
                citations.append(c["id"])
    # documents tool already returns claim_id at top level (handled by query_claims branch)
    return list(dict.fromkeys(citations))  # dedupe, preserve order


async def _decide(
    *,
    deps: ClaimsAgentDeps,
    query: str,
    scratchpad: list[dict[str, Any]],
    context: dict[str, Any] | None,
    history: list[BaseMessage],
) -> ReActDecision:
    system_prompt = deps.prompts.load("react", "v1")
    tool_catalog = deps.tool_catalog
    context_section = ""
    if context:
        focus_claim = context.get("focus_claim_id")
        focus_provider = context.get("focus_provider_id")
        focus_asegurado = context.get("focus_asegurado_id")
        if focus_claim:
            context_section = (
                f"\n## Contexto del UI\nEl analista está mirando el caso "
                f"`{focus_claim}`. Si la pregunta es ambigua, asumí que se refiere a ese siniestro.\n\n"
            )
        elif focus_provider:
            context_section = (
                f"\n## Contexto del UI\nEl analista está mirando el proveedor "
                f"`{focus_provider}`. Llamá a `get_provider_detail` al inicio para conocer "
                f"su ficha antes de responder preguntas de seguimiento.\n\n"
            )
        elif focus_asegurado:
            context_section = (
                f"\n## Contexto del UI\nEl analista está mirando el asegurado "
                f"`{focus_asegurado}`. Llamá a `get_asegurado_detail` al inicio para conocer "
                f"su perfil antes de responder preguntas de seguimiento.\n\n"
            )
    history_section = (
        f"## Historial de conversación\n{_format_history(history, current_query=query)}\n\n"
    )
    user_payload = (
        f"## Pregunta del analista\n{query}\n\n"
        f"{context_section}"
        f"{history_section}"
        f"## Herramientas disponibles\n```json\n{tool_catalog}\n```\n\n"
        f"## scratchpad (pasos anteriores)\n```json\n{_format_scratchpad(scratchpad)}\n```\n\n"
        "Decide el próximo paso. Si ya tenés suficiente información, responde "
        '`{"action":"finish",...}`. Si no, llamá a una herramienta. Usá el '
        "historial para resolver referencias del tipo 'ese proveedor', 'el caso anterior'."
    )
    response_format = ResponseFormat(
        schema_name="ReActDecision",
        json_schema=ReActDecision.model_json_schema(),
    )
    result = await deps.llm.complete(
        messages=[
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_payload),
        ],
        model=deps.llm_model,
        response_format=response_format,
    )
    return ReActDecision.model_validate_json(result.message.content)


def make_react_step(
    deps: ClaimsAgentDeps,
) -> Callable[[ClaimsAgentState], Awaitable[dict[str, Any]]]:
    async def react_step(state: ClaimsAgentState) -> dict[str, Any]:
        step_count = (state.get("step_count") or 0) + 1
        scratchpad = list(state.get("scratchpad") or [])
        call_id = uuid.uuid4().hex

        # 1. Ask the LLM what to do next. Defensive: any LLM/parse failure is
        #    treated as "finish" so the loop never spins on bad output.
        try:
            decision = await _decide(
                deps=deps,
                query=state["query"],
                scratchpad=scratchpad,
                context=state.get("context"),
                history=list(state.get("messages") or []),
            )
        except (ValidationError, ValueError) as exc:
            entry = ScratchpadEntry(
                step=step_count,
                thought=f"[decisión inválida] {exc}",
                call_id=call_id,
            )
            return {"step_count": step_count, "scratchpad": [entry.model_dump()], "finished": True}

        # 2. Finishing branch — LLM thinks it has enough info.
        if decision.action == "finish" or step_count >= deps.max_react_steps:
            reason = decision.reason or "max_react_steps alcanzado"
            trace = decision.thought
            if decision.action == "finish":
                trace = f"{trace} | motivo: {reason}"
            entry = ScratchpadEntry(step=step_count, thought=trace, call_id=call_id)
            return {
                "step_count": step_count,
                "scratchpad": [entry.model_dump()],
                "finished": True,
            }

        # 3. Tool-use branch — dispatch by name through the registry.
        tool_name = decision.tool or ""
        tool_entry = deps.tool_registry.get(tool_name)
        if tool_entry is None:
            entry = ScratchpadEntry(
                step=step_count,
                thought=decision.thought,
                tool=tool_name,
                args=decision.args,
                observation={"error": f"herramienta desconocida: {tool_name!r}"},
                call_id=call_id,
            )
            # Don't finish — let the LLM retry on the next iteration with the error in scratchpad.
            return {"step_count": step_count, "scratchpad": [entry.model_dump()]}

        # Resolve the last user message for the focused-question heuristic.
        last_user_msg = state["query"]
        _ctx = state.get("context") or {}
        _focus = FocusContext(
            claim_id=_ctx.get("focus_claim_id"),
            provider_id=_ctx.get("focus_provider_id"),
            asegurado_id=_ctx.get("focus_asegurado_id"),
        )
        try:
            tool_output = await tool_entry.run_with_context(
                llm_args=decision.args or {},
                focus=_focus,
                last_user_message=last_user_msg,
            )
            observation_payload: Any = tool_output.model_dump(mode="json")
        except (ValueError, ValidationError) as exc:
            observation_payload = {"error": str(exc)}

        entry = ScratchpadEntry(
            step=step_count,
            thought=decision.thought,
            tool=tool_name,
            args=decision.args,
            observation=observation_payload,
            call_id=call_id,
        )
        # `tool_results` is the SSE-visible projection (what the chat panel renders
        # as ToolCallEvent / ToolResultEvent). Scratchpad is the LLM-facing memory.
        new_tool_result: dict[str, Any] = {
            "tool": tool_name,
            "call_id": call_id,
            "args": decision.args or {},
            "result": observation_payload,
        }
        new_citations = _extract_citations(tool_name, observation_payload)

        return {
            "step_count": step_count,
            "scratchpad": [entry.model_dump()],
            "tool_results": [new_tool_result],
            "citations": new_citations,
        }

    return react_step
