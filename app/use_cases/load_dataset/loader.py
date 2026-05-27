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

from sqlalchemy import text
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


async def _compute_aggregates(session: AsyncSession) -> None:
    """Backfill columns that aggregate over the freshly-loaded rows."""
    # asegurados.num_polizas — count of polizas per asegurado.
    await session.execute(
        text(
            """
            UPDATE asegurados a SET num_polizas = sub.cnt
            FROM (
              SELECT id_asegurado, COUNT(*) AS cnt
              FROM polizas GROUP BY id_asegurado
            ) sub
            WHERE a.id_asegurado = sub.id_asegurado
            """
        )
    )

    # asegurados.reclamos_ultimos_12_meses — siniestros with fecha_ocurrencia
    # within the trailing 365 days of the most recent claim in the dataset.
    await session.execute(
        text(
            """
            WITH ref AS (SELECT MAX(fecha_ocurrencia) AS d FROM siniestros),
                 recent AS (
                   SELECT s.id_asegurado, COUNT(*) AS cnt
                   FROM siniestros s, ref
                   WHERE s.fecha_ocurrencia >= ref.d - INTERVAL '365 days'
                   GROUP BY s.id_asegurado
                 )
            UPDATE asegurados a
            SET reclamos_ultimos_12_meses = COALESCE(recent.cnt, 0)
            FROM recent
            WHERE a.id_asegurado = recent.id_asegurado
            """
        )
    )

    # siniestros.historial_siniestros_asegurado — count of strictly prior
    # siniestros for the same asegurado (lifetime, not 12-mo).
    await session.execute(
        text(
            """
            UPDATE siniestros s
            SET historial_siniestros_asegurado = sub.cnt
            FROM (
              SELECT a.id_siniestro,
                     (SELECT COUNT(*) FROM siniestros b
                      WHERE b.id_asegurado = a.id_asegurado
                        AND b.fecha_ocurrencia < a.fecha_ocurrencia) AS cnt
              FROM siniestros a
            ) sub
            WHERE s.id_siniestro = sub.id_siniestro
            """
        )
    )

    # beneficiarios_proveedores aggregates from linked siniestros.
    await session.execute(
        text(
            """
            UPDATE beneficiarios_proveedores p SET
              reclamos_asociados = COALESCE(sub.casos, 0),
              monto_promedio_reclamado = COALESCE(sub.avg_monto, 0)
            FROM (
              SELECT s.beneficiario AS id,
                     COUNT(*) AS casos,
                     AVG(s.monto_reclamado) AS avg_monto
              FROM siniestros s
              WHERE s.beneficiario IS NOT NULL
              GROUP BY s.beneficiario
            ) sub
            WHERE p.id_proveedor = sub.id
            """
        )
    )

    # porcentaje_casos_observados = yellow+red / total per proveedor.
    await session.execute(
        text(
            """
            UPDATE beneficiarios_proveedores p
            SET porcentaje_casos_observados = sub.ratio
            FROM (
              SELECT s.beneficiario AS id,
                     CASE WHEN COUNT(*) = 0 THEN 0
                          ELSE SUM(CASE WHEN cs.tier IN ('amarillo','rojo')
                                        THEN 1 ELSE 0 END)::float / COUNT(*)
                     END AS ratio
              FROM siniestros s
              JOIN claim_scores cs ON cs.claim_id = s.id_siniestro
              WHERE s.beneficiario IS NOT NULL
              GROUP BY s.beneficiario
            ) sub
            WHERE p.id_proveedor = sub.id
            """
        )
    )


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
