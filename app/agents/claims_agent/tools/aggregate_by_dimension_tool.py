"""Tool for Q3 / Q4 / Q5 / Q6 / Q8 / Q10 — group-by aggregations.

Q3  proveedores que concentran más alertas
Q4  ramos con mayor % de casos sospechosos
Q5  ciudades con mayor concentración de alertas
Q6  asegurados con mayor frecuencia de reclamos
Q8  casos con montos atípicos  (handled in the aggregate node via dimension picker)
Q10 patrones repetidos en reclamos sospechosos
"""

from pydantic import BaseModel, Field

from app.agents.claims_agent.tools.ports import ClaimQueries
from app.agents.claims_agent.tools.types import AggregateDimension, AggregateRow, TierFilter
from app.schemas.chat.stream.chart_hint import ChartHint
from app.schemas.claim import ClaimDetail


class AggregateByDimensionInput(BaseModel):
    dimension: AggregateDimension
    tier: TierFilter = "amarillo+rojo"
    top_n: int = Field(10, ge=1, le=50)
    filter_claim_id: str | None = Field(
        default=None,
        description=(
            "Set ONLY when the analyst is asking about a specific case in scope "
            "(e.g. 'este caso', 'este siniestro'). Usually injected automatically from the UI context."
        ),
    )
    filter_provider_id: str | None = Field(
        default=None,
        description=(
            "Set ONLY when the analyst asks about 'este proveedor' / 'ese proveedor' "
            "while a provider context is active. Injected automatically by the dispatcher."
        ),
    )
    filter_asegurado_id: str | None = Field(
        default=None,
        description=(
            "Set ONLY when the analyst asks about 'este asegurado' / 'ese asegurado' "
            "while an asegurado context is active. Injected automatically by the dispatcher."
        ),
    )
    chart_hint: ChartHint | None = Field(
        default=None,
        description=(
            "Set ONLY when the analyst explicitly asked for a chart/visualization in this turn "
            "(e.g. 'gráfico', 'chart', 'scatterplot', 'visualiza', 'muéstrame un diagrama'). "
            "Leave null otherwise — chart emission is opt-in."
        ),
    )


class AggregateByDimensionOutput(BaseModel):
    dimension: AggregateDimension
    tier: TierFilter
    rows: list[AggregateRow]


class AggregateByDimensionTool:
    name = "aggregate_by_dimension"
    description = (
        "Agrupa siniestros por dimensión (proveedor, ramo, ciudad o asegurado) y "
        "devuelve el ranking de los que concentran más alertas, con un ejemplo de "
        "siniestro citable."
    )

    def __init__(self, queries: ClaimQueries) -> None:
        self._queries = queries

    @property
    def input_schema(self) -> dict[str, object]:
        return AggregateByDimensionInput.model_json_schema()

    async def run(self, args: AggregateByDimensionInput) -> AggregateByDimensionOutput:
        rows = await self._queries.aggregate(
            dimension=args.dimension, tier=args.tier, top_n=args.top_n
        )

        if args.filter_claim_id is not None:
            # Scope aggregation to rows that include the focused claim as an example.
            # For most dimensions a single claim appears in at most one bucket.
            scoped = [r for r in rows if r.example_claim_id == args.filter_claim_id]
            if not scoped:
                # The claim didn't surface as an example — fetch its detail to build a
                # synthetic one-row result so the agent can still say something useful.
                detail = await self._queries.get_detail(args.filter_claim_id)
                if detail is not None:
                    dim_key = _dimension_key(args.dimension, detail)
                    if dim_key is not None:
                        scoped = [
                            AggregateRow(
                                key=dim_key,
                                count=1,
                                pct=0.0,
                                example_claim_id=detail.id,
                            )
                        ]
            rows = scoped

        return AggregateByDimensionOutput(dimension=args.dimension, tier=args.tier, rows=rows)


def _dimension_key(dimension: AggregateDimension, detail: ClaimDetail) -> str | None:
    """Extract the aggregation key for a given dimension from a ClaimDetail."""
    match dimension:
        case "proveedor":
            return detail.proveedor
        case "ramo":
            return detail.ramo
        case "ciudad":
            return detail.ciudad
        case "asegurado":
            return detail.asegurado
        case _:
            return None
