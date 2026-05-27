"""Port the 5 agent tools depend on for claim data.

Concrete impl lives in `app/use_cases/claim_queries/` (backed by `claims_repo`
once Miquel's lane lands V1+V2). Tests use `InMemoryClaimQueries` so the agent
suite never needs a real DB.

Per backend CLAUDE.md §5: graph nodes never reach into DB directly — they call
ports. Tools are the port-facing seam.
"""

from typing import Protocol, runtime_checkable

from app.agents.claims_agent.tools.types import (
    AggregateDimension,
    AggregateRow,
    ExecutiveSummary,
    MissingDocClaim,
    TierFilter,
)
from app.schemas.claim import ClaimDetail, ClaimSummary


@runtime_checkable
class ClaimQueries(Protocol):
    """Read-side queries the claims agent's 5 tools delegate to."""

    async def list_top_risk(
        self, *, top_n: int = 10, tier: TierFilter = "amarillo+rojo"
    ) -> list[ClaimSummary]:
        """Q1: top-N claims by risk score (desc)."""

    async def get_detail(self, claim_id: str) -> ClaimDetail | None:
        """Q2: full claim detail. Returns None if not found."""

    async def aggregate(
        self,
        *,
        dimension: AggregateDimension,
        tier: TierFilter = "amarillo+rojo",
        top_n: int = 10,
    ) -> list[AggregateRow]:
        """Q3-Q6, Q8, Q10: group-by counts with example claim IDs."""

    async def missing_documents(
        self, *, top_n: int = 10, tier: TierFilter = "amarillo+rojo"
    ) -> list[MissingDocClaim]:
        """Q7: critical claims with missing legal docs."""

    async def claims_near_policy_start(
        self, *, window_days: int = 10, top_n: int = 10
    ) -> list[ClaimSummary]:
        """Q9: claims that occurred close to policy start (high FS-01 risk)."""

    async def recommend_review(self, *, top_n: int = 5) -> list[ClaimSummary]:
        """Q12: which cases should the analyst review first?"""

    async def executive_summary(self) -> ExecutiveSummary:
        """Q11: aggregate snapshot of the most critical claims."""
