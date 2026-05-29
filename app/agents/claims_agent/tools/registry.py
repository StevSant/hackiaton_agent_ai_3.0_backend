"""Runtime tool registry — maps tool name → callable runner + input schema.

The ReAct loop uses this to dispatch the LLM's chosen tool by name without
big if/else chains. Tools are constructed in `ClaimsAgentDeps` (one per query
slice); this registry just indexes them.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agents.claims_agent._tool_dispatcher import FocusContext, inject_focus_context
from app.agents.claims_agent.tools import (
    AggregateByDimensionInput,
    AggregateByDimensionTool,
    CrearDocumentoInput,
    CrearDocumentoTool,
    GetAseguradoDetailInput,
    GetAseguradoDetailTool,
    GetClaimDetailInput,
    GetClaimDetailTool,
    GetProviderDetailInput,
    GetProviderDetailTool,
    MissingDocumentsInput,
    MissingDocumentsTool,
    QueryClaimsInput,
    QueryClaimsTool,
    SummarizeCriticalInput,
    SummarizeCriticalTool,
    VerifyVehicleInput,
    VerifyVehicleTool,
)
from app.agents.claims_agent.tools.tool_spec_view import ToolSpecView


@dataclass(slots=True)
class ToolEntry:
    name: str
    description: str
    input_model: type[BaseModel]
    invoke: Callable[[BaseModel], Awaitable[BaseModel]]

    def spec(self) -> ToolSpecView:
        return ToolSpecView(
            name=self.name,
            description=self.description,
            input_schema=self.input_model.model_json_schema(),
        )

    async def run_raw(self, args: dict[str, Any]) -> BaseModel:
        try:
            parsed = self.input_model.model_validate(args or {})
        except ValidationError as exc:
            raise ValueError(f"invalid args for tool '{self.name}': {exc}") from exc
        return await self.invoke(parsed)

    async def run_with_context(
        self,
        *,
        llm_args: dict[str, Any],
        focus_claim_id: str | None = None,
        focus: FocusContext | None = None,
        last_user_message: str,
    ) -> BaseModel:
        """Dispatch the tool after injecting focus context when appropriate.

        Accepts either a `FocusContext` object (new callers) or a bare
        `focus_claim_id` string (legacy callers — still supported).
        """
        if focus is None:
            focus = FocusContext(claim_id=focus_claim_id)
        enriched = inject_focus_context(
            tool_name=self.name,
            llm_args=llm_args,
            focus=focus,
            last_user_message=last_user_message,
        )
        return await self.run_raw(enriched)


def build_tool_registry(
    *,
    query_claims: QueryClaimsTool,
    get_claim_detail: GetClaimDetailTool,
    aggregate_by_dimension: AggregateByDimensionTool,
    missing_documents: MissingDocumentsTool,
    summarize_critical: SummarizeCriticalTool,
    crear_documento: CrearDocumentoTool | None = None,
    get_provider_detail: GetProviderDetailTool | None = None,
    get_asegurado_detail: GetAseguradoDetailTool | None = None,
    verify_vehicle: VerifyVehicleTool | None = None,
) -> dict[str, ToolEntry]:
    """Bundle every tool into a name-indexed registry.

    Names match each tool's `.name` attribute — that's the surface the LLM
    sees in the ReAct prompt and chooses by.
    """
    entries = [
        ToolEntry(
            name=aggregate_by_dimension.name,
            description=aggregate_by_dimension.description,
            input_model=AggregateByDimensionInput,
            invoke=aggregate_by_dimension.run,  # type: ignore[arg-type]
        ),
        ToolEntry(
            name=get_claim_detail.name,
            description=get_claim_detail.description,
            input_model=GetClaimDetailInput,
            invoke=get_claim_detail.run,  # type: ignore[arg-type]
        ),
        ToolEntry(
            name=missing_documents.name,
            description=missing_documents.description,
            input_model=MissingDocumentsInput,
            invoke=missing_documents.run,  # type: ignore[arg-type]
        ),
        ToolEntry(
            name=query_claims.name,
            description=query_claims.description,
            input_model=QueryClaimsInput,
            invoke=query_claims.run,  # type: ignore[arg-type]
        ),
        ToolEntry(
            name=summarize_critical.name,
            description=summarize_critical.description,
            input_model=SummarizeCriticalInput,
            invoke=summarize_critical.run,  # type: ignore[arg-type]
        ),
    ]
    if crear_documento is not None:
        entries.append(
            ToolEntry(
                name=crear_documento.name,
                description=crear_documento.description,
                input_model=CrearDocumentoInput,
                invoke=crear_documento.run,  # type: ignore[arg-type]
            )
        )
    if get_provider_detail is not None:
        entries.append(
            ToolEntry(
                name=get_provider_detail.name,
                description=get_provider_detail.description,
                input_model=GetProviderDetailInput,
                invoke=get_provider_detail.run,  # type: ignore[arg-type]
            )
        )
    if get_asegurado_detail is not None:
        entries.append(
            ToolEntry(
                name=get_asegurado_detail.name,
                description=get_asegurado_detail.description,
                input_model=GetAseguradoDetailInput,
                invoke=get_asegurado_detail.run,  # type: ignore[arg-type]
            )
        )
    if verify_vehicle is not None:
        entries.append(
            ToolEntry(
                name=verify_vehicle.name,
                description=verify_vehicle.description,
                input_model=VerifyVehicleInput,
                invoke=verify_vehicle.run,  # type: ignore[arg-type]
            )
        )
    return {e.name: e for e in entries}
