"""load_dataset — ingests data/synthetic/claims.json into the normalized DB tables.

Each claim in the JSON (a pre-scored ClaimDetail) is upserted into:
  asegurados → polizas → siniestros → documentos
  beneficiarios_proveedores (when proveedor present)
  claim_scores

A final aggregation pass fills count-based columns that depend on multiple
rows (num_polizas, reclamos_ultimos_12_meses, historial_siniestros_asegurado,
proveedor reclamos/monto/observados).

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

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.claim_score import ClaimScore
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
_DEMO_PATH = Path("data/synthetic/demo_claims.json")
logger = logging.getLogger(__name__)


async def load_dataset(
    session: AsyncSession,
    path: Path = _DATASET_PATH,
    demo_path: Path = _DEMO_PATH,
) -> int:
    """Upsert claims from *path* (and the demo overlay) into the database.

    Demo claims take precedence: any synthetic row with a colliding `id` is
    dropped so the on-screen cases (SIN-2026-NNNNN) are the canonical ones.

    Returns the number of claims processed.
    Raises FileNotFoundError when the dataset file is absent.
    """
    claims = load_saved(path)
    if claims is None:
        raise FileNotFoundError(f"Dataset not found: {path}")

    demo = load_saved(demo_path) or []
    demo_ids = {c.id for c in demo}
    merged = [*demo, *(c for c in claims if c.id not in demo_ids)]

    for claim in merged:
        await _upsert_claim(session, claim)

    await session.commit()
    await _compute_aggregates(session)
    await session.commit()
    logger.info(
        "load_dataset: upserted %d claims (synthetic=%d, demo=%d) + aggregates",
        len(merged), len(claims), len(demo),
    )
    return len(merged)


# ---------------------------------------------------------------------------
# Post-ingest aggregation pass
# ---------------------------------------------------------------------------


from app.use_cases.load_dataset._aggregates import compute_aggregates as _compute_aggregates


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

    # 6. ClaimScore — PK is auto-increment but claim_id has a UNIQUE constraint,
    # so merge() can't upsert blindly (it would INSERT a duplicate). Look up the
    # existing row's id by claim_id first so merge() does UPDATE not INSERT.
    score_row = claim_detail_to_score(claim)
    existing_score_id = (
        await session.execute(
            select(ClaimScore.id).where(ClaimScore.claim_id == claim.id)
        )
    ).scalar_one_or_none()
    if existing_score_id is not None:
        score_row.id = existing_score_id
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
