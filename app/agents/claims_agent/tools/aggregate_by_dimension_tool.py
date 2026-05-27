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


class AggregateByDimensionInput(BaseModel):
    dimension: AggregateDimension
    tier: TierFilter = "amarillo+rojo"
    top_n: int = Field(10, ge=1, le=50)


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
        return AggregateByDimensionOutput(dimension=args.dimension, tier=args.tier, rows=rows)
