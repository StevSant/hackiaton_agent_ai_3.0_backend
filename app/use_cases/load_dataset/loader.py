"""load_dataset — ingests data/synthetic/claims.json into the normalized DB tables.

Each claim in the JSON (a pre-scored ClaimDetail) is upserted into:
  asegurados → polizas → siniestros → documentos
  beneficiarios_proveedores (when proveedor present)
  claim_scores

All operations are idempotent (SQLAlchemy session.merge = upsert on PK).

Usage (CLI):
    uv run python -m app.use_cases.load_dataset

Usage (programmatic):
    from sqlalchemy.ext.asyncio import AsyncSession
    await load_dataset(session)
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.claim import ClaimDetail
from app.use_cases.generate_dataset.runner import load_saved
from app.use_cases.load_dataset._mapping import (
    claim_detail_to_asegurado,
    claim_detail_to_documentos,
    claim_detail_to_poliza,
    claim_detail_to_proveedor,
    claim_detail_to_score,
    claim_detail_to_siniestro,
)

_DATASET_PATH = Path("data/synthetic/claims.json")
logger = logging.getLogger(__name__)


async def load_dataset(
    session: AsyncSession,
    path: Path = _DATASET_PATH,
) -> int:
    """Upsert all claims from *path* into the database.

    Returns the number of claims processed.
    Raises FileNotFoundError when the dataset file is absent.
    """
    claims = load_saved(path)
    if claims is None:
        raise FileNotFoundError(f"Dataset not found: {path}")

    for claim in claims:
        await _upsert_claim(session, claim)

    await session.commit()
    logger.info("load_dataset: upserted %d claims", len(claims))
    return len(claims)


async def _upsert_claim(session: AsyncSession, claim: ClaimDetail) -> None:
    """Upsert a single ClaimDetail into all relevant tables."""
    # 1. Asegurado (must exist before poliza FK)
    asegurado = claim_detail_to_asegurado(claim)
    await session.merge(asegurado)
    await session.flush()

    # 2. Poliza (must exist before siniestro FK)
    poliza = claim_detail_to_poliza(claim)
    await session.merge(poliza)
    await session.flush()

    # 3. Proveedor (no FK dependency — upsert independently)
    proveedor = claim_detail_to_proveedor(claim)
    if proveedor is not None:
        await session.merge(proveedor)
        await session.flush()

    # 4. Siniestro
    siniestro = claim_detail_to_siniestro(claim)
    await session.merge(siniestro)
    await session.flush()

    # 5. Documentos (cascade-delete-orphan on siniestro, so upsert individually)
    for doc in claim_detail_to_documentos(claim):
        await session.merge(doc)
    await session.flush()

    # 6. ClaimScore
    score_row = claim_detail_to_score(claim)
    await session.merge(score_row)
    await session.flush()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


async def _main() -> None:
    """Run the loader from the command line against the configured DATABASE_URL."""
    from app.infrastructure.db.engine import create_engine, create_session_factory

    engine = create_engine()
    factory = create_session_factory(engine)
    async with factory() as session:
        count = await load_dataset(session)
    await engine.dispose()
    print(f"load_dataset: {count} claims upserted successfully.")


if __name__ == "__main__":
    asyncio.run(_main())
