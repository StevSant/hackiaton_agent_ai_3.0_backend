"""Tool for Q1 / Q9 / Q12 — ranked claim lists.

Q1  "¿Cuáles son los 10 siniestros con mayor riesgo de posible fraude?"
Q9  "¿Qué siniestros ocurrieron cerca del inicio de la póliza?"
Q12 "Recomienda qué casos debería revisar primero el analista."

`mode` discriminates between the three. Default `top_risk` answers Q1.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.agents.claims_agent.tools.types import TierFilter
from app.schemas.chat.stream.chart_hint import ChartHint
from app.schemas.claim import ClaimSummary

QueryMode = Literal["top_risk", "near_policy_start", "recommend_review"]


class QueryClaimsInput(BaseModel):
    mode: QueryMode = "top_risk"
    top_n: int = Field(10, ge=1, le=50)
    tier: TierFilter = "amarillo+rojo"
    window_days: int = Field(10, ge=1, le=365, description="Only used when mode=near_policy_start")
    chart_hint: ChartHint | None = Field(
        default=None,
        description=(
            "Set ONLY when the analyst explicitly asked for a chart/visualization in this turn "
            "(e.g. 'gráfico', 'chart', 'scatterplot', 'visualiza', 'muéstrame un diagrama'). "
            "Leave null otherwise — chart emission is opt-in."
        ),
    )


class QueryClaimsOutput(BaseModel):
    mode: QueryMode
    claims: list[ClaimSummary]


class QueryClaimsTool:
    name = "query_claims"
    description = (
        "Devuelve una lista ordenada de siniestros para preguntas tipo "
        "'top-N por riesgo', 'cerca del inicio de póliza' o 'qué revisar primero'."
    )

    def __init__(self, queries: ClaimQueries) -> None:
        self._queries = queries

    @property
    def input_schema(self) -> dict[str, object]:
        return QueryClaimsInput.model_json_schema()

    async def run(self, args: QueryClaimsInput) -> QueryClaimsOutput:
        match args.mode:
            case "top_risk":
                claims = await self._queries.list_top_risk(top_n=args.top_n, tier=args.tier)
            case "near_policy_start":
                claims = await self._queries.claims_near_policy_start(
                    window_days=args.window_days, top_n=args.top_n
                )
            case "recommend_review":
                claims = await self._queries.recommend_review(top_n=args.top_n)
        return QueryClaimsOutput(mode=args.mode, claims=claims)
