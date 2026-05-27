"""Backfill realistic display names for asegurados and providers.

Two cleanup passes that run after the main ingest:

1. `_backfill_asegurado_names` — any `asegurados.nombre` left NULL by older
   imports gets a deterministic Ecuadorian full name derived from the row's
   `id_asegurado`. Same name pools as the synthetic generator, so the result
   is stable and analyst-friendly.

2. `_backfill_provider_names` — providers whose `nombre` is still an internal
   code (`PROV-LISTA-NNN`, `PROV-OBS-NNN`) get replaced with a deterministic
   Ecuadorian business name from the same `prefijo + qualifier` pools used
   by the generator. The id_proveedor seeds the picks so re-runs are stable.

Both passes are idempotent — a second run finds nothing to update.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.use_cases.generate_dataset._pools import (
    APELLIDOS,
    CODE_PROVIDER_PATTERNS,
    NOMBRES_FEMENINOS,
    NOMBRES_MASCULINOS,
    PROVEEDOR_PREFIJOS,
    PROVEEDOR_QUALIFIERS,
)


def _stable_int(seed: str, lo: int, hi: int) -> int:
    """Deterministic int in [lo, hi] from a string seed (md5)."""
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)  # noqa: S324  not crypto
    return lo + (h % (hi - lo + 1))


def _stable_pick(seed: str, items: list[str]) -> str:
    return items[_stable_int(seed, 0, len(items) - 1)]


def _ecuador_full_name_for_id(id_asegurado: str) -> str:
    """Deterministic Spanish-Ecuador full name seeded by the asegurado ID."""
    gender = _stable_int(f"ase-gender-{id_asegurado}", 0, 1)
    pool = NOMBRES_MASCULINOS if gender == 0 else NOMBRES_FEMENINOS
    nombre = _stable_pick(f"ase-nombre-{id_asegurado}", pool)
    apellido1 = _stable_pick(f"ase-ap1-{id_asegurado}", APELLIDOS)
    apellido2 = _stable_pick(f"ase-ap2-{id_asegurado}", APELLIDOS)
    return f"{nombre} {apellido1} {apellido2}"


def _ecuador_provider_name_for_id(id_proveedor: str) -> str:
    """Deterministic Ecuadorian business name seeded by the provider ID."""
    prefijo = _stable_pick(f"prov-prefijo-{id_proveedor}", PROVEEDOR_PREFIJOS)
    qualifier = _stable_pick(f"prov-qualifier-{id_proveedor}", PROVEEDOR_QUALIFIERS)
    return f"{prefijo} {qualifier}"


def _looks_like_provider_code(value: str) -> bool:
    """True when `value` matches an internal-code prefix (PROV-LISTA, PROV-OBS, …)."""
    upper = value.upper()
    return any(upper.startswith(p) for p in CODE_PROVIDER_PATTERNS)


async def backfill_display_names(session: AsyncSession) -> tuple[int, int]:
    """Run both cleanup passes. Returns (asegurados_updated, proveedores_updated)."""
    asegurados_updated = await _backfill_asegurado_names(session)
    proveedores_updated = await _backfill_provider_names(session)
    return asegurados_updated, proveedores_updated


async def _backfill_asegurado_names(session: AsyncSession) -> int:
    rows = (
        await session.execute(
            text("SELECT id_asegurado FROM asegurados WHERE nombre IS NULL")
        )
    ).all()
    if not rows:
        return 0
    for (id_asegurado,) in rows:
        nombre = _ecuador_full_name_for_id(id_asegurado)
        await session.execute(
            text("UPDATE asegurados SET nombre = :nombre WHERE id_asegurado = :id"),
            {"nombre": nombre, "id": id_asegurado},
        )
    return len(rows)


async def _backfill_provider_names(session: AsyncSession) -> int:
    rows = (
        await session.execute(
            text(
                "SELECT id_proveedor, nombre FROM beneficiarios_proveedores "
                "WHERE nombre IS NULL OR nombre = '' "
                "   OR nombre ~ '^PROV-(LISTA|OBS)-'"
            )
        )
    ).all()
    if not rows:
        return 0
    for id_proveedor, _old in rows:
        nombre = _ecuador_provider_name_for_id(id_proveedor)
        await session.execute(
            text(
                "UPDATE beneficiarios_proveedores SET nombre = :nombre "
                "WHERE id_proveedor = :id"
            ),
            {"nombre": nombre, "id": id_proveedor},
        )
    return len(rows)
