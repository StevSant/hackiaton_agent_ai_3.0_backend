"""Port the agent tools depend on for claim data.

Concrete impl lives in `app/infrastructure/db/db_claim_queries.py`. Tests use
`InMemoryClaimQueries` so the agent suite never needs a real DB.

Per backend CLAUDE.md §5: graph nodes never reach into DB directly — they call
ports. Tools are the port-facing seam.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from app.agents.claims_agent.tools.types import (
    AggregateDimension,
    AggregateRow,
    ExecutiveSummary,
    MissingDocClaim,
    TierFilter,
)
from app.schemas.claim import ClaimDetail, ClaimSummary

if TYPE_CHECKING:
    from app.agents.claims_agent.tools.get_asegurado_detail_tool import (
        GetAseguradoDetailOutput,
    )
    from app.agents.claims_agent.tools.get_provider_detail_tool import (
        GetProviderDetailOutput,
    )


@runtime_checkable
class ClaimQueries(Protocol):
    """Read-side queries the claims agent tools delegate to."""

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

    async def get_provider_detail(
        self, provider_id: str, *, top_claims: int = 5
    ) -> "GetProviderDetailOutput | None":
        """Ficha completa de un proveedor + sus top-N siniestros por score."""

    async def get_asegurado_detail(
        self, asegurado_id: str, *, top_claims: int = 5
    ) -> "GetAseguradoDetailOutput | None":
        """Ficha completa de un asegurado + sus top-N siniestros por score."""
