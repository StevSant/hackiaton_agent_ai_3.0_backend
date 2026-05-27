from pydantic import BaseModel


class AggregateRow(BaseModel):
    """One row in an `aggregate_by_dimension` result.

    `key` is the dimension value ("P-0042" for proveedor, "Vehículos" for ramo).
    `count` is the number of suspicious claims for that key.
    `pct` is `count / total` * 100 — useful when answering "qué porcentaje".
    `example_claim_id` lets the LLM cite a concrete case in its NL answer.
    """

    key: str
    count: int
    pct: float
    example_claim_id: str | None = None
