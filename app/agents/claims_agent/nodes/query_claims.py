"""query_claims node — Q1 / Q9 / Q12 (ranked lists).

Picks the tool mode from keywords in the query, calls `QueryClaimsTool`, appends
the tool result + citations to state.
"""

import re
import uuid
from collections.abc import Awaitable, Callable

from app.agents.claims_agent.dependencies import ClaimsAgentDeps
from app.agents.claims_agent.state import ClaimsAgentState
from app.agents.claims_agent.tools import QueryClaimsInput, QueryMode


def _pick_mode(query: str) -> QueryMode:
    q = query.lower()
    if "inicio" in q and ("poliza" in q or "póliza" in q):
        return "near_policy_start"
    if "primero" in q or "recomend" in q or "revisar primero" in q:
        return "recommend_review"
    return "top_risk"


def _pick_top_n(query: str, default: int = 10) -> int:
    match = re.search(r"\b(top[\s-]*)?(\d{1,3})\b", query)
    if not match:
        return default
    n = int(match.group(2))
    return max(1, min(n, 50))


def make_query_claims(deps: ClaimsAgentDeps) -> Callable[[ClaimsAgentState], Awaitable[dict]]:
    async def query_claims(state: ClaimsAgentState) -> dict:
        query = state["query"]
        args = QueryClaimsInput(mode=_pick_mode(query), top_n=_pick_top_n(query))
        output = await deps.query_claims.run(args)
        call_id = uuid.uuid4().hex

        return {
            "tool_results": [
                {
                    "tool": deps.query_claims.name,
                    "call_id": call_id,
                    "args": args.model_dump(),
                    "result": output.model_dump(mode="json"),
                }
            ],
            "citations": [c.id for c in output.claims],
        }

    return query_claims
