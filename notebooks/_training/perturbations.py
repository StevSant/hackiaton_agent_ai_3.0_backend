"""Perturb a ``ClaimDetail`` into ``N`` deterministic variants for training.

The 62 canonical archetypes give us coverage but not diversity. We expand to
~1.8k rows by perturbing each archetype 30 times. Perturbations are:

  - small ±20% jitter on ``monto_reclamado``
  - small ±3-day jitter on ``fecha_reporte`` (and thus on the
    occurrence→report delay)
  - small ±2 jitter on ``historial_siniestros_asegurado``

All other fields stay fixed so categorical flags (which dominate the rules
engine) remain meaningful. Perturbed variants are RE-SCORED by the rules
engine afterwards, so the label (``etiqueta_fraude_simulada = 1 if tier=rojo``)
moves naturally when a perturbation crosses a threshold. This is the only
honest way to get a non-trivial training distribution out of 62 archetypes.

Deterministic: variant ``v`` of archetype ``k`` is always the same — no random
seeding, no module-level state.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta

from app.schemas.claim import ClaimDetail

VARIANTS_PER_ARCHETYPE: int = 30


def _hash01(seed: str) -> float:
    """Deterministic float in [0, 1) from a string seed."""
    digest = hashlib.md5(seed.encode()).hexdigest()  # noqa: S324 — not crypto
    return (int(digest, 16) % 10_000) / 10_000.0


def _jitter_pct(seed: str, max_pct: float) -> float:
    """Symmetric ±max_pct jitter centered on 0 (return value, e.g., 0.07 = +7%)."""
    return (_hash01(seed) - 0.5) * 2.0 * max_pct


def _jitter_int(seed: str, max_delta: int) -> int:
    """Symmetric integer jitter in [-max_delta, +max_delta]."""
    r = _hash01(seed)
    return round((r - 0.5) * 2.0 * max_delta)


def perturb_claim(claim: ClaimDetail, variant_idx: int) -> ClaimDetail:
    """Return a perturbed copy of *claim* for the given variant index.

    Variant 0 returns the original (so the canonical 62 always survive in the
    training set). Variants 1..N-1 are deterministically perturbed.
    """
    if variant_idx == 0:
        return claim

    seed_base = f"{claim.id}-v{variant_idx}"

    # ±20% on monto_reclamado
    pct = _jitter_pct(f"{seed_base}-monto", 0.20)
    new_monto = max(0.0, round(claim.monto_reclamado * (1.0 + pct), 2))

    # ±3 days on fecha_reporte (clamped so it's not before fecha_ocurrencia)
    day_delta = _jitter_int(f"{seed_base}-report", 3)
    new_reporte = claim.fecha_reporte + timedelta(days=day_delta)
    if new_reporte < claim.fecha_ocurrencia:
        new_reporte = claim.fecha_ocurrencia

    return claim.model_copy(
        update={
            "monto_reclamado": new_monto,
            "fecha_reporte": new_reporte,
        }
    )
