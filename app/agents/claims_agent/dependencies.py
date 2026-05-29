"""Concrete dependency bundle the claims-agent graph carries via closure.

The graph's nodes are pure functions; their external dependencies (LLM, tools,
prompt loader, tool registry) get bound to them at graph-build time via the
`make_*` factories under `nodes/`. This bundle is the typed shape of those deps.

Wired in `app/api/deps.py::get_ask_agent` once per request.
"""

import json
from dataclasses import dataclass, field

from app.agents.claims_agent.tools import (
    AggregateByDimensionTool,
    AnalyzeReviewersTool,
    CrearDocumentoTool,
    GetAseguradoDetailTool,
    GetClaimDetailTool,
    GetProviderDetailTool,
    MissingDocumentsTool,
    QueryClaimsTool,
    SummarizeCriticalTool,
    VerifyVehicleTool,
)
from app.agents.claims_agent.tools.registry import ToolEntry, build_tool_registry
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
    crear_documento: CrearDocumentoTool | None = None
    get_provider_detail: GetProviderDetailTool | None = None
    get_asegurado_detail: GetAseguradoDetailTool | None = None
    verify_vehicle: VerifyVehicleTool | None = None
    analyze_reviewers: AnalyzeReviewersTool | None = None
    max_react_steps: int = 3
    # Built in __post_init__ from the tools above. Indexed by tool name —
    # the ReAct loop dispatches by string match against the LLM's decision.
    tool_registry: dict[str, ToolEntry] = field(default_factory=dict)
    # Pre-rendered tool catalog string for the ReAct prompt. Same content on
    # every iteration / request, so we compute once here instead of paying the
    # JSON-dump cost ~3x per agent turn inside react_step.
    tool_catalog: str = ""

    def __post_init__(self) -> None:
        if not self.tool_registry:
            self.tool_registry = build_tool_registry(
                query_claims=self.query_claims,
                get_claim_detail=self.get_claim_detail,
                aggregate_by_dimension=self.aggregate_by_dimension,
                missing_documents=self.missing_documents,
                summarize_critical=self.summarize_critical,
                crear_documento=self.crear_documento,
                get_provider_detail=self.get_provider_detail,
                get_asegurado_detail=self.get_asegurado_detail,
                verify_vehicle=self.verify_vehicle,
                analyze_reviewers=self.analyze_reviewers,
            )
        if not self.tool_catalog:
            entries = [entry.spec().model_dump() for entry in self.tool_registry.values()]
            self.tool_catalog = json.dumps(entries, ensure_ascii=False, indent=2)
