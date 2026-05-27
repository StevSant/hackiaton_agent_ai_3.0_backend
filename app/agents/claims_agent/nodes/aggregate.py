"""aggregate node — Q3 / Q4 / Q5 / Q6 / Q8 / Q10 (group-bys).

Detects the dimension from query keywords (proveedor / ramo / ciudad / asegurado),
calls `AggregateByDimensionTool`, returns rows + an `example_claim_id` per row for
citations.
"""

import uuid
from collections.abc import Awaitable, Callable

from app.agents.claims_agent.dependencies import ClaimsAgentDeps
from app.agents.claims_agent.state import ClaimsAgentState
from app.agents.claims_agent.tools import AggregateByDimensionInput
from app.agents.claims_agent.tools.types import AggregateDimension

_DIMENSION_KEYWORDS: list[tuple[tuple[str, ...], AggregateDimension]] = [
    (("proveedor", "proveedores"), "proveedor"),
    (("ramo", "ramos"), "ramo"),
    (("ciudad", "ciudades"), "ciudad"),
    (("asegurado", "asegurados"), "asegurado"),
    (("patron", "patrones", "patrón", "monto", "montos"), "proveedor"),
]


def _pick_dimension(query: str) -> AggregateDimension:
    q = query.lower()
    for keywords, dim in _DIMENSION_KEYWORDS:
        if any(k in q for k in keywords):
            return dim
    return "proveedor"


def make_aggregate(deps: ClaimsAgentDeps) -> Callable[[ClaimsAgentState], Awaitable[dict]]:
    async def aggregate(state: ClaimsAgentState) -> dict:
        args = AggregateByDimensionInput(dimension=_pick_dimension(state["query"]))
        output = await deps.aggregate_by_dimension.run(args)
        call_id = uuid.uuid4().hex

        return {
            "tool_results": [
                {
                    "tool": deps.aggregate_by_dimension.name,
                    "call_id": call_id,
                    "args": args.model_dump(),
                    "result": output.model_dump(mode="json"),
                }
            ],
            "citations": [row.example_claim_id for row in output.rows if row.example_claim_id],
        }

    return aggregate
