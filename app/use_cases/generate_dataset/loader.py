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


def _fallback_claims() -> list[ClaimDetail]:
    from tests.fixtures.claims import ALL_FIXTURES

    return list(ALL_FIXTURES)


def build_synthetic_queries(path: Path = _DATASET_PATH) -> InMemoryClaimQueries:
    """Load the synthetic dataset or fall back to fixtures.

    Returns an ``InMemoryClaimQueries`` instance ready to serve claims.
    """
    claims = load_saved(path)
    if claims is None or len(claims) == 0:
        claims = _fallback_claims()
    return InMemoryClaimQueries(claims=claims)


class SyntheticClaimQueries(InMemoryClaimQueries):
    """``ClaimQueries`` backed by the committed synthetic dataset.

    Inherits all query methods from ``InMemoryClaimQueries``; the only
    difference is the source of the claim list (JSON file vs. hand-crafted
    fixtures).
    """

    def __init__(self, path: Path = _DATASET_PATH) -> None:
        claims = load_saved(path) or _fallback_claims()
        super().__init__(claims=claims)
