"""Generator for importable sample files under ``data/samples/``.

Produces three JSON variants and one CSV file, all using the same Ecuador
archetypes from ``_archetypes.py`` and the seed pools loaded from
``data/config/`` via ``_pools/``.

    claims.dev.json   ~ 40 claims  (fast local testing)
    claims.test.json  ~ 80 claims  (CI / demo rehearsal)
    claims.prod.json  ~ 180 claims (near-realistic data volume for Supabase load)
    claims.sample.csv               handful of rows showing the CSV import format

The generator is deterministic: running it twice produces the same files.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from random import Random

from app.schemas.claim import ClaimDetail
from app.use_cases.generate_dataset._archetypes import ARCHETYPES, ClaimArchetype
from app.use_cases.generate_dataset._claim_builder import build_claim

_SAMPLES_DIR = Path("data/samples")

# Deterministic seed for the archetype-order permutation. Bumping this number
# reshuffles small samples (claims.dev.json) — only do so intentionally.
_PERMUTATION_SEED = 7


# ---------------------------------------------------------------------------
# Sampling helpers
# ---------------------------------------------------------------------------


def _archetype_order() -> list[int]:
    """Deterministic permutation of archetype indices.

    ``ARCHETYPES`` groups archetypes by tier and adds new ramos at the end, so
    a naive ``i % archetype_count`` makes the dev sample (40 claims) hit only
    the first ~40 archetypes — which are all Vehículos. Shuffling once with a
    fixed seed spreads non-Vehículos ramos throughout, so even the smallest
    sample shows ramo diversity in the providers / network UI.
    """
    indices = list(range(len(ARCHETYPES)))
    Random(_PERMUTATION_SEED).shuffle(indices)
    return indices


def _build_sample(
    target: int,
    base_offset: int = 0,
) -> list[ClaimDetail]:
    """Build *target* claims by cycling through a permuted ARCHETYPES order.

    ``base_offset`` allows different variants to produce distinct IDs so their
    claim IDs don't collide when both are loaded into the same DB.
    Real Ecuadorian names are already injected by ``build_claim`` (no separate
    rename pass needed).
    """
    claims: list[ClaimDetail] = []
    order = _archetype_order()
    archetype_count = len(order)
    for i in range(target):
        arch_idx = order[i % archetype_count]
        archetype: ClaimArchetype = ARCHETYPES[arch_idx]
        # Global index so IDs are unique across variants
        global_idx = base_offset + i + 1
        claim, _ = build_claim(archetype, global_idx)
        # Prefix ID with variant marker so there are no collisions
        prefixed = claim.model_copy(
            update={
                "id": f"IMP-{global_idx:05d}",
                "poliza": f"POL-IMP-{global_idx:05d}",
            }
        )
        claims.append(prefixed)
    return claims


# ---------------------------------------------------------------------------
# CSV export (denormalised — one row per claim)
# ---------------------------------------------------------------------------


_CSV_COLUMNS = [
    "id", "ramo", "cobertura", "asegurado", "asegurado_id", "poliza",
    "ciudad", "fecha_ocurrencia", "fecha_reporte",
    "fecha_inicio_poliza", "fecha_fin_poliza",
    "monto_reclamado", "suma_asegurada", "estado", "sucursal",
    "proveedor", "descripcion", "score", "nivel",
]


def _claim_to_csv_row(c: ClaimDetail) -> dict[str, object]:
    return {
        "id": c.id,
        "ramo": c.ramo,
        "cobertura": c.cobertura,
        "asegurado": c.asegurado,
        "asegurado_id": c.asegurado_id,
        "poliza": c.poliza,
        "ciudad": c.ciudad,
        "fecha_ocurrencia": str(c.fecha_ocurrencia),
        "fecha_reporte": str(c.fecha_reporte),
        "fecha_inicio_poliza": str(c.fecha_inicio_poliza) if c.fecha_inicio_poliza else "",
        "fecha_fin_poliza": str(c.fecha_fin_poliza) if c.fecha_fin_poliza else "",
        "monto_reclamado": c.monto_reclamado,
        "suma_asegurada": c.suma_asegurada,
        "estado": c.estado,
        "sucursal": c.sucursal,
        "proveedor": c.proveedor or "",
        "descripcion": c.descripcion,
        "score": c.score,
        "nivel": c.nivel.value,
    }


def _save_csv(claims: list[ClaimDetail], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for c in claims:
            writer.writerow(_claim_to_csv_row(c))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_samples(out_dir: Path = _SAMPLES_DIR) -> dict[str, int]:
    """Generate all sample files and return a dict of {filename: row_count}."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Each variant uses a non-overlapping ID range so they can coexist in DB
    dev = _build_sample(40, base_offset=0)
    test = _build_sample(80, base_offset=40)
    prod = _build_sample(180, base_offset=120)

    # JSON variants
    variants = [
        ("claims.dev.json", dev),
        ("claims.test.json", test),
        ("claims.prod.json", prod),
    ]
    for name, claims in variants:
        payload = [c.model_dump(mode="json") for c in claims]
        (out_dir / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # CSV sample — first 10 rows of the dev variant for documentation
    _save_csv(dev[:10], out_dir / "claims.sample.csv")

    return {
        "claims.dev.json": len(dev),
        "claims.test.json": len(test),
        "claims.prod.json": len(prod),
        "claims.sample.csv": 10,
    }
