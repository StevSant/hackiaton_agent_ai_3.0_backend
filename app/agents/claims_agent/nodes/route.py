"""Intent classifier node — uses the LLM with structured output (`response_format`).

Sets `state.intent` to one of the 5 intents. Fallback heuristics handle malformed
LLM output (defensive: a bad parse shouldn't break the demo).
"""

import re
from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from app.agents.claims_agent.dependencies import ClaimsAgentDeps
from app.agents.claims_agent.state import ClaimsAgentState, Intent
from app.infrastructure.llm.types import Message, ResponseFormat


class IntentChoice(BaseModel):
    intent: Intent


_AGGREGATE_RE = re.compile(
    r"\b(proveedor(?:es)?|ramo(?:s)?|ciudad(?:es)?|asegurado(?:s)?|"
    r"patron(?:es)?|montos? atipicos?)\b",
    re.IGNORECASE,
)
_DOCS_RE = re.compile(r"\bdocumentos?\b.*\b(falta|incompleto|complet)", re.IGNORECASE)
_SUMMARY_RE = re.compile(r"\bresumen ejecutivo|\bsnapshot\b|\bpanorama\b", re.IGNORECASE)
_CLAIM_RE = re.compile(r"\bSIN-\w+\b", re.IGNORECASE)

_HEURISTICS: list[tuple[re.Pattern[str], Intent]] = [
    (_CLAIM_RE, "explain_case"),
    (_DOCS_RE, "documents"),
    (_AGGREGATE_RE, "aggregate"),
    (_SUMMARY_RE, "summarize"),
]


def _heuristic_intent(query: str) -> Intent:
    for pattern, intent in _HEURISTICS:
        if pattern.search(query):
            return intent
    return "query_claims"


def make_route(deps: ClaimsAgentDeps) -> Callable[[ClaimsAgentState], Awaitable[dict]]:
    async def route(state: ClaimsAgentState) -> dict:
        query = state["query"]

        # Hard signal from the UI: if the chat panel pinned a claim, that's an
        # explicit "explain this case" intent — short-circuit the LLM call.
        ctx = state.get("context") or {}
        if isinstance(ctx, dict) and ctx.get("focus_claim_id"):
            return {"intent": "explain_case"}

        system_prompt = deps.prompts.load("route", "v1")
        response_format = ResponseFormat(
            schema_name="IntentChoice",
            json_schema=IntentChoice.model_json_schema(),
        )

        try:
            result = await deps.llm.complete(
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=query),
                ],
                model=deps.llm_model,
                response_format=response_format,
            )
            parsed = IntentChoice.model_validate_json(result.message.content)
            intent: Intent = parsed.intent
        except Exception:
            intent = _heuristic_intent(query)

        return {"intent": intent}

    return route
