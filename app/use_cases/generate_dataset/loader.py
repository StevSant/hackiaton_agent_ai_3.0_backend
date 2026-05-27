"""SyntheticClaimQueries — ``ClaimQueries`` port impl over the committed dataset.

Loads the pre-scored JSON from ``data/synthetic/claims.json`` on first access.
Falls back to the hand-crafted fixtures (3 claims) if the file is absent.

**Double-scoring decision**: claims in the synthetic dataset are already scored
at generation time with a fully-populated ``RuleContext``.  ``get_claim_detail``
is patched to skip re-scoring when ``claim.alertas`` is non-empty (i.e. the
claim was served from this loader).  This preserves the rich demo scores and
avoids clobbering them with the context-poor ``RuleContext.from_claim`` path.
The live-scoring path remains active for un-scored DB claims (future).
"""

from __future__ import annotations

from pathlib import Path

from app.schemas.claim import ClaimDetail
from app.use_cases.claim_queries.in_memory_claim_queries import InMemoryClaimQueries
from app.use_cases.generate_dataset.runner import load_saved

_DATASET_PATH = Path("data/synthetic/claims.json")
_DEMO_PATH = Path("data/synthetic/demo_claims.json")


def _fallback_claims() -> list[ClaimDetail]:
    from tests.fixtures.claims import ALL_FIXTURES

    return list(ALL_FIXTURES)


def _merge_demo_first(
    demo: list[ClaimDetail] | None, synthetic: list[ClaimDetail]
) -> list[ClaimDetail]:
    """Demo claims take precedence: same ``id`` from synthetic is dropped.

    The demo set mirrors the frontend's hand-authored cases (SIN-2026-08412 and
    its 17 siblings) — the analyst sees them on screen, so the agent must serve
    those exact rows when its ``get_claim_detail`` tool is invoked.
    """
    if not demo:
        return synthetic
    demo_ids = {c.id for c in demo}
    return [*demo, *(c for c in synthetic if c.id not in demo_ids)]


def build_synthetic_queries(
    path: Path = _DATASET_PATH, demo_path: Path = _DEMO_PATH
) -> InMemoryClaimQueries:
    """Load the synthetic dataset (+ demo overrides) or fall back to fixtures."""
    synthetic = load_saved(path) or []
    demo = load_saved(demo_path)
    merged = _merge_demo_first(demo, synthetic)
    if not merged:
        merged = _fallback_claims()
    return InMemoryClaimQueries(claims=merged)


class SyntheticClaimQueries(InMemoryClaimQueries):
    """``ClaimQueries`` backed by the committed synthetic dataset.

    Inherits all query methods from ``InMemoryClaimQueries``; the only
    difference is the source of the claim list (JSON file vs. hand-crafted
    fixtures). Demo claims from ``data/synthetic/demo_claims.json`` (which
    mirror the frontend mock) are prepended so the agent serves the cases the
    analyst actually sees on screen.
    """

    def __init__(
        self, path: Path = _DATASET_PATH, demo_path: Path = _DEMO_PATH
    ) -> None:
        synthetic = load_saved(path) or []
        demo = load_saved(demo_path)
        merged = _merge_demo_first(demo, synthetic) or _fallback_claims()
        super().__init__(claims=merged)
