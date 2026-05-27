"""documents node — Q7 (missing legal documents)."""

import uuid
from collections.abc import Awaitable, Callable

from app.agents.claims_agent.dependencies import ClaimsAgentDeps
from app.agents.claims_agent.state import ClaimsAgentState
from app.agents.claims_agent.tools import MissingDocumentsInput


def make_documents(deps: ClaimsAgentDeps) -> Callable[[ClaimsAgentState], Awaitable[dict]]:
    async def documents(state: ClaimsAgentState) -> dict:
        args = MissingDocumentsInput()
        output = await deps.missing_documents.run(args)
        call_id = uuid.uuid4().hex

        return {
            "tool_results": [
                {
                    "tool": deps.missing_documents.name,
                    "call_id": call_id,
                    "args": args.model_dump(),
                    "result": output.model_dump(mode="json"),
                }
            ],
            "citations": [row.claim_id for row in output.claims],
        }

    return documents
