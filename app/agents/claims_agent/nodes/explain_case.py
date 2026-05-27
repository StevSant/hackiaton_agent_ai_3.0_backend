"""explain_case node — Q2 (per-claim breakdown).

Extracts the `SIN-XXXX` claim ID from the query (or from `state.context`), calls
`GetClaimDetailTool`, returns the full detail with activations + ml factors +
similar narratives.
"""

import re
import uuid
from collections.abc import Awaitable, Callable

from app.agents.claims_agent.dependencies import ClaimsAgentDeps
from app.agents.claims_agent.state import ClaimsAgentState
from app.agents.claims_agent.tools import GetClaimDetailInput

_CLAIM_ID = re.compile(r"\b(SIN-[A-Z0-9_-]+)\b", re.IGNORECASE)


def _extract_claim_id(state: ClaimsAgentState) -> str | None:
    ctx = state.get("context") or {}
    focus = ctx.get("focus_claim_id")
    if isinstance(focus, str) and focus:
        return focus
    match = _CLAIM_ID.search(state["query"])
    return match.group(1).upper() if match else None


def make_explain_case(deps: ClaimsAgentDeps) -> Callable[[ClaimsAgentState], Awaitable[dict]]:
    async def explain_case(state: ClaimsAgentState) -> dict:
        claim_id = _extract_claim_id(state)
        call_id = uuid.uuid4().hex

        if not claim_id:
            return {
                "tool_results": [
                    {
                        "tool": deps.get_claim_detail.name,
                        "call_id": call_id,
                        "args": {},
                        "result": {"found": False, "error": "no claim id in query"},
                    }
                ],
                "citations": [],
            }

        args = GetClaimDetailInput(claim_id=claim_id)
        output = await deps.get_claim_detail.run(args)
        return {
            "tool_results": [
                {
                    "tool": deps.get_claim_detail.name,
                    "call_id": call_id,
                    "args": args.model_dump(),
                    "result": output.model_dump(mode="json"),
                }
            ],
            "citations": [claim_id] if output.found else [],
        }

    return explain_case
