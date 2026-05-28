"""seed_vehicle_chassis — mint synthetic chassis on every vehicle siniestro.

Workflow:
1. Query the DISTINCT marca + modelo across every vehicle ``Siniestro`` (those
   with marca + modelo + año + placa) and call ``build_vehicle_vocab(...)`` so
   every declared value in the DB is indexable by the codec (the previous bug
   was that real values like ``Toyota / RAV4`` were outside the generator pools).
2. For each vehicle claim, write a deterministic synthetic chassis. The legit
   majority encodes the DECLARED spec, so decode agrees with the claim.
3. A deterministic ~``mismatch_count`` subset encodes a DIFFERENT in-vocab spec
   (a different marca + modelo, also drawn from the vocab), so decode contradicts
   the declared vehicle and FS-15 fires. The subset is chosen by stable ordering
   (id_siniestro) + stride, so re-running the seed produces the same set.

The vocab JSON is committed; encode/decode resolve indices against it, so the
offline ``RegistryVehicleDecoder`` decodes back to exactly what was seeded.

Usage (CLI):
    uv run python -m app.use_cases.seed_vehicle_chassis

Programmatic:
    await seed_vehicle_chassis(session, mismatch_count=15)
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.vehicle_identity import (
    VehicleSpec,
    VehicleVocab,
    build_vehicle_vocab,
    encode_synthetic_chassis,
)
from app.infrastructure.db.models.siniestro import Siniestro

logger = logging.getLogger(__name__)


def _has_vehicle(sin: Siniestro) -> bool:
    """True when the claim carries a full declared vehicle we can encode."""
    return bool(sin.marca and sin.modelo and sin.anio and sin.placa)


def _mismatched_spec(declared: VehicleSpec, vocab: VehicleVocab) -> VehicleSpec:
    """Return a spec with a DIFFERENT, in-vocab marca + modelo than *declared*.

    Deterministic: rotates marca/modelo to the next entry in the persisted vocab,
    keeping the year so only marca/modelo discrepancies drive FS-15 (single, clear
    cause). The vocab always holds the declared value (built in step 1), so the
    rotated neighbour is guaranteed to exist and to differ when the vocab has ≥ 2
    entries in each dimension.
    """
    marca_idx = vocab.index_marca(declared.marca)
    modelo_idx = vocab.index_modelo(declared.modelo)
    nueva_marca = vocab.marcas[(marca_idx + 1) % len(vocab.marcas)]
    nuevo_modelo = vocab.modelos[(modelo_idx + 1) % len(vocab.modelos)]
    return VehicleSpec(marca=nueva_marca, modelo=nuevo_modelo, anio=declared.anio)


async def seed_vehicle_chassis(
    session: AsyncSession,
    *,
    mismatch_count: int = 15,
) -> dict[str, int]:
    """Build the vocab from DB values, then mint chassis; flag ~N as mismatched.

    Args:
        session:        AsyncSession (committed at the end).
        mismatch_count: Approximate number of claims that get a contradicting
                        chassis so FS-15 fires on them.

    Returns:
        ``{"updated": U, "mismatched": M}`` — claims given a chassis, and how
        many of those got a deliberately contradicting one.
    """
    sins: list[Siniestro] = list(
        (await session.execute(select(Siniestro).order_by(Siniestro.id_siniestro)))
        .scalars()
        .all()
    )
    vehiculo_sins = [s for s in sins if _has_vehicle(s)]

    # Step 1: persist a vocabulary that covers every declared make/model so the
    # codec can index them (this is the fix for the out-of-pool ValueError).
    distinct_marcas = {s.marca for s in vehiculo_sins if s.marca}
    distinct_modelos = {s.modelo for s in vehiculo_sins if s.modelo}
    vocab = build_vehicle_vocab(distinct_marcas, distinct_modelos)

    # Deterministic stride so ~mismatch_count claims are picked evenly.
    stride = max(1, len(vehiculo_sins) // mismatch_count) if mismatch_count > 0 else 0
    mismatched_ids: set[str] = set()
    if stride:
        for sin in vehiculo_sins[::stride]:
            if len(mismatched_ids) >= mismatch_count:
                break
            mismatched_ids.add(sin.id_siniestro)

    updated = 0
    mismatched = 0
    for sin in vehiculo_sins:
        declared = VehicleSpec(marca=sin.marca, modelo=sin.modelo, anio=sin.anio)
        if sin.id_siniestro in mismatched_ids:
            spec = _mismatched_spec(declared, vocab)
            mismatched += 1
        else:
            spec = declared
        sin.chasis = encode_synthetic_chassis(spec)
        updated += 1

    await session.commit()
    logger.info("seed_vehicle_chassis: updated=%d mismatched=%d", updated, mismatched)
    return {"updated": updated, "mismatched": mismatched}


async def _main() -> None:
    """Run the seed from the command line against the configured DATABASE_URL."""
    from app.infrastructure.db.engine import create_engine, create_session_factory

    engine = create_engine()
    factory = create_session_factory(engine)
    async with factory() as session:
        counts = await seed_vehicle_chassis(session)
    await engine.dispose()
    print(
        f"seed_vehicle_chassis: updated={counts['updated']} "
        f"mismatched={counts['mismatched']}."
    )


if __name__ == "__main__":
    asyncio.run(_main())
