"""Map an `Asegurado` entity to `AseguradoOut` (best-effort, no aggregation).

Used by the single-record create/update endpoints. Aggregate fields
(`casos`, `alertas`, `monto`, `ramos`) come from the grouped query in
`list_asegurados`; here they default to zero. The frontend reloads the full
list after a mutation, so this response is just an optimistic echo.
"""

from __future__ import annotations

from app.infrastructure.db.models.asegurado import Asegurado
from app.schemas.asegurados import AseguradoOut


def asegurado_to_out(a: Asegurado) -> AseguradoOut:
    return AseguradoOut(
        id_asegurado=a.id_asegurado,
        nombre=a.nombre or f"Asegurado {a.id_asegurado[-4:]}",
        segmento=a.segmento,
        ciudad=a.ciudad,
        antiguedad=a.antiguedad,
        num_polizas=a.num_polizas,
        reclamos_ultimos_12_meses=a.reclamos_ultimos_12_meses,
        mora_actual=a.mora_actual,
        score_cliente_simulado=a.score_cliente_simulado,
        casos=0,
        alertas=0,
        monto=0.0,
        ramos=[],
    )
