"""compose node — final Spanish renderer with citations.

Takes the accumulated `tool_results` + `citations` and produces the analyst-facing
answer. The system + compose prompts (`claims_system.v1.md`, `compose.v1.md`)
carry the voice, formatting, and "never accuse" rules.
"""

import json
import uuid
from collections.abc import Awaitable, Callable

from app.agents.claims_agent.dependencies import ClaimsAgentDeps
from app.agents.claims_agent.state import ClaimsAgentState
from app.infrastructure.llm.types import Message


def _serialize_tool_results(results: list[dict]) -> str:
    return json.dumps(results, ensure_ascii=False, indent=2, default=str)


def make_compose(deps: ClaimsAgentDeps) -> Callable[[ClaimsAgentState], Awaitable[dict]]:
    async def compose(state: ClaimsAgentState) -> dict:
        system_prompt = deps.prompts.load("claims_system", "v1")
        compose_prompt = deps.prompts.load("compose", "v1")
        tool_results = state.get("tool_results") or []
        citations = state.get("citations") or []

        user_payload = (
            f"## Pregunta del analista\n{state['query']}\n\n"
            f"## tool_results\n```json\n{_serialize_tool_results(tool_results)}\n```\n\n"
            f"## citations\n{', '.join(citations) if citations else '—'}\n\n"
            f"Componé la respuesta final siguiendo las reglas de `compose.v1`."
        )

        result = await deps.llm.complete(
            messages=[
                Message(role="system", content=system_prompt),
                Message(role="system", content=compose_prompt),
                Message(role="user", content=user_payload),
            ],
            model=deps.llm_model,
        )

        return {
            "answer": result.message.content,
            "message_id": uuid.uuid4().hex,
        }

    return compose
