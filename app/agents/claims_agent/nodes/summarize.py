"""summarize node — Q11 (executive summary)."""

import uuid
from collections.abc import Awaitable, Callable

from app.agents.claims_agent.dependencies import ClaimsAgentDeps
from app.agents.claims_agent.state import ClaimsAgentState
from app.agents.claims_agent.tools import SummarizeCriticalInput


def make_summarize(deps: ClaimsAgentDeps) -> Callable[[ClaimsAgentState], Awaitable[dict]]:
    async def summarize(state: ClaimsAgentState) -> dict:
        args = SummarizeCriticalInput()
        output = await deps.summarize_critical.run(args)
        call_id = uuid.uuid4().hex

        return {
            "tool_results": [
                {
                    "tool": deps.summarize_critical.name,
                    "call_id": call_id,
                    "args": args.model_dump(),
                    "result": output.model_dump(mode="json"),
                }
            ],
            "citations": [c.id for c in output.summary.top_rojo],
        }

    return summarize
