"""Concrete dependency bundle the claims-agent graph carries through `RunnableConfig`.

LangGraph nodes are kept as pure functions; their external dependencies (LLM,
tools, prompt loader) are passed via `config["configurable"]`. This bundle is
the typed shape of that dict — so nodes don't deal with stringly-typed lookups.

Wired in `app/use_cases/ask_agent.py` once per request.
"""

from dataclasses import dataclass

from app.agents.claims_agent.tools import (
    AggregateByDimensionTool,
    GetClaimDetailTool,
    MissingDocumentsTool,
    QueryClaimsTool,
    SummarizeCriticalTool,
)
from app.infrastructure.llm import LLMProvider, PromptLoader


@dataclass(slots=True)
class ClaimsAgentDeps:
    llm: LLMProvider
    llm_model: str
    prompts: PromptLoader
    query_claims: QueryClaimsTool
    get_claim_detail: GetClaimDetailTool
    aggregate_by_dimension: AggregateByDimensionTool
    missing_documents: MissingDocumentsTool
    summarize_critical: SummarizeCriticalTool
