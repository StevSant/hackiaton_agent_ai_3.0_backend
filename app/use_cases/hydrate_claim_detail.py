"""hydrate_claim_detail — assemble a ClaimDetail from a Siniestro + related rows.

Shared by the rescore path (``reanalyze_claim``) and the on-demand NLP analyzer
(``analyze_claim_narrative_persisted``) so both hydrate identically — neither
hand-rolls the relationship loads.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.asegurado import Asegurado
from app.infrastructure.db.models.claim_score import ClaimScore
from app.infrastructure.db.models.documento import Documento
from app.infrastructure.db.models.poliza import Poliza
from app.infrastructure.db.models.proveedor import Proveedor
from app.infrastructure.db.models.siniestro import Siniestro
from app.schemas.claim import ClaimDetail
from app.use_cases.load_dataset._mapping import rows_to_claim_detail


async def hydrate_claim_detail(session: AsyncSession, sin: Siniestro) -> ClaimDetail:
    """Assemble a ClaimDetail from a Siniestro + its related rows."""
    pol: Poliza | None = await session.get(Poliza, sin.id_poliza)
    score_row: ClaimScore | None = (
        (
            await session.execute(
                select(ClaimScore).where(ClaimScore.claim_id == sin.id_siniestro)
            )
        )
        .scalars()
        .first()
    )
    docs = list(
        (
            await session.execute(
                select(Documento).where(Documento.id_siniestro == sin.id_siniestro)
            )
        )
        .scalars()
        .all()
    )
    proveedor: Proveedor | None = (
        await session.get(Proveedor, sin.beneficiario) if sin.beneficiario else None
    )
    asegurado: Asegurado | None = await session.get(Asegurado, sin.id_asegurado)
    return rows_to_claim_detail(sin, pol, score_row, docs, proveedor, asegurado=asegurado)
