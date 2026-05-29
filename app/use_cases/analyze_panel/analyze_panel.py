"""AnalyzePanel — multi-agent fraud panel orchestrator (additive; never touches claims_agent).

Flow per claim:
  panel_start
  → R1: each specialist streams narration (agent_token, round 1) then emits a
        structured verdict (agent_verdict). Run concurrently; streams interleave.
  → R2: each specialist re-reads peers' R1 verdicts, streams narration
        (agent_token, round 2) then emits a structured rebuttal (agent_rebuttal).
  → Moderador: streams synthesis (moderator_token) then emits consensus.
  → done

Parallel token streams from the concurrent specialists are merged into one
ordered async iterator via an asyncio.Queue. Each LLM call's user payload is
tagged `[especialista:{id}] [fase:{narracion|veredicto|replica|consenso}]` so
prompts (and the fake LLM in tests) match deterministically.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.claims_agent.tools import ClaimQueries
from app.agents.fraud_panel import MODERATOR_PROMPT_ID, PANEL_ROSTER, Specialist
from app.domain.anomaly import AnomalyDetector
from app.domain.ml import FraudClassifier
from app.infrastructure.llm import LLMProvider, Message, PromptLoader, ResponseFormat
from app.infrastructure.reviews.ports import ReviewsStore
from app.schemas.claim import ClaimDetail
from app.schemas.panel import (
    AgentRebuttalData,
    AgentRebuttalEvent,
    AgentTokenData,
    AgentTokenEvent,
    AgentVerdictData,
    AgentVerdictEvent,
    ConsensusData,
    ConsensusEvent,
    ModeratorTokenData,
    ModeratorTokenEvent,
    PanelConsensus,
    PanelDoneData,
    PanelDoneEvent,
    PanelErrorData,
    PanelErrorEvent,
    PanelRosterEntry,
    PanelStartData,
    PanelStartEvent,
    PanelStreamEvent,
    SpecialistRebuttal,
    SpecialistVerdict,
)
from app.use_cases.get_claim_detail import get_claim_detail

logger = logging.getLogger(__name__)

_Producer = Callable[["asyncio.Queue[Any]"], Awaitable[None]]
_SENTINEL = object()
_M = TypeVar("_M", bound=BaseModel)


class AnalyzePanel:
    """Orchestrates one multi-agent panel run over a single claim."""

    def __init__(
        self,
        *,
        llm: LLMProvider,
        prompts: PromptLoader,
        queries: ClaimQueries,
        model: str,
        reviews_store: ReviewsStore | None = None,
        classifier: FraudClassifier | None = None,
        detector: AnomalyDetector | None = None,
        read_session: AsyncSession | None = None,
    ) -> None:
        self._llm = llm
        self._prompts = prompts
        self._queries = queries
        self._model = model
        self._reviews_store = reviews_store
        self._classifier = classifier
        self._detector = detector
        # The session backing `queries`/`reviews_store`. The panel reads the claim
        # up front then runs a long, DB-free LLM debate — we release this pooled
        # connection after the reads instead of holding it idle for the whole run.
        self._read_session = read_session

    async def run(self, claim_id: str) -> AsyncGenerator[PanelStreamEvent, None]:
        try:
            claim = await get_claim_detail(
                self._queries,
                claim_id,
                reviews_store=self._reviews_store,
                classifier=self._classifier,
                detector=self._detector,
            )
        except Exception as exc:
            logger.exception("panel: get_claim_detail failed for %s", claim_id)
            yield PanelErrorEvent(data=PanelErrorData(code="claim_fetch_error", message=str(exc)))
            yield PanelDoneEvent(data=PanelDoneData(claim_id=claim_id))
            return
        if claim is None:
            yield PanelErrorEvent(
                data=PanelErrorData(
                    code="not_found", message=f"Siniestro {claim_id} no encontrado."
                )
            )
            yield PanelDoneEvent(data=PanelDoneData(claim_id=claim_id))
            return

        yield PanelStartEvent(
            data=PanelStartData(
                claim_id=claim_id,
                roster=[
                    PanelRosterEntry(agent_id=s.id, display_name=s.display_name, lens=s.lens)
                    for s in PANEL_ROSTER
                ],
            )
        )

        # Ground the Documentos/Red specialist with real provider KPIs (not just
        # the name) so its "red"/network reasoning has substance.
        slice_extras: dict[str, dict[str, Any]] = {}
        provider_stats = await self._provider_stats(claim)
        if provider_stats is not None:
            slice_extras["documentos_red"] = {"proveedor_stats": provider_stats}

        # Reads are done (claim detail + provider stats). Everything below is a
        # connection-free LLM debate, so hand the pooled connection back now
        # instead of pinning it idle for the whole multi-LLM run. Best-effort:
        # the debate must proceed even if the release hiccups.
        if self._read_session is not None:
            try:
                await self._read_session.commit()
            except Exception:  # pragma: no cover - releasing an idle connection
                logger.debug("panel: could not release read session", exc_info=True)

        # --- R1: parallel narration + verdict. Capture verdicts as they stream by.
        verdicts: dict[str, SpecialistVerdict] = {}
        async for ev in self._drain(
            [self._r1_producer(s, claim, slice_extras.get(s.id)) for s in PANEL_ROSTER]
        ):
            if isinstance(ev, AgentVerdictEvent):
                verdicts[ev.data.agent_id] = ev.data.verdict
            yield ev

        # --- R2: each specialist reacts to peers' R1 verdicts.
        rebuttals: dict[str, SpecialistRebuttal] = {}
        async for ev in self._drain(
            [self._r2_producer(s, claim, verdicts) for s in PANEL_ROSTER]
        ):
            if isinstance(ev, AgentRebuttalEvent):
                rebuttals[ev.data.agent_id] = ev.data.rebuttal
            yield ev

        # --- Moderator synthesis (single stream).
        async for ev in self._moderator(claim, verdicts, rebuttals):
            yield ev

        yield PanelDoneEvent(data=PanelDoneData(claim_id=claim_id))

    # ----- round drivers -------------------------------------------------

    async def _provider_stats(self, claim: ClaimDetail) -> dict[str, Any] | None:
        """Fetch provider KPIs for the Documentos/Red lens (best-effort)."""
        if not claim.proveedor:
            return None
        try:
            detail = await self._queries.get_provider_detail(claim.proveedor)
        except Exception:
            logger.debug("panel: provider lookup failed for %s", claim.proveedor)
            return None
        prov = getattr(detail, "provider", None)
        if prov is None:
            return None
        return {
            "casos_asociados": prov.casos,
            "alertas": prov.alertas,
            "monto_total": prov.monto,
            "lista_restrictiva": prov.lista_restrictiva,
            "ramos": prov.ramos,
        }

    def _r1_producer(
        self,
        specialist: Specialist,
        claim: ClaimDetail,
        extra: dict[str, Any] | None = None,
    ) -> _Producer:
        async def produce(queue: asyncio.Queue[Any]) -> None:
            try:
                system = self._prompts.load(specialist.prompt_id, "v1")
                slice_data = specialist.slice_fn(claim)
                if extra:
                    slice_data = {**slice_data, **extra}
                slice_json = json.dumps(slice_data, ensure_ascii=False, default=str)
                # narration (streamed)
                await self._stream_tokens(
                    queue,
                    agent_id=specialist.id,
                    round_num=1,
                    system=system,
                    user=(
                        f"[especialista:{specialist.id}] [fase:narracion]\n"
                        f"Analiza este siniestro desde tu lente y explica tu razonamiento "
                        f"en 2-3 frases.\n\nDatos:\n{slice_json}"
                    ),
                )
                # structured verdict
                verdict = await self._structured(
                    system=system,
                    user=(
                        f"[especialista:{specialist.id}] [fase:veredicto]\n"
                        f"Emite tu VEREDICTO estructurado del siniestro.\n\nDatos:\n{slice_json}"
                    ),
                    schema=SpecialistVerdict,
                )
                await queue.put(
                    AgentVerdictEvent(
                        data=AgentVerdictData(agent_id=specialist.id, verdict=verdict)
                    )
                )
            except Exception as exc:  # graceful degradation — panel never crashes
                logger.exception("panel R1 specialist %s failed", specialist.id)
                await queue.put(
                    PanelErrorEvent(
                        data=PanelErrorData(
                            agent_id=specialist.id, code="specialist_error", message=str(exc)
                        )
                    )
                )
                await queue.put(
                    AgentVerdictEvent(
                        data=AgentVerdictData(
                            agent_id=specialist.id,
                            verdict=SpecialistVerdict(
                                nivel=claim.nivel,
                                dictamen="sin opinión (el análisis de este especialista falló)",
                                puntos_clave=[],
                                confianza="baja",
                                citas=[],
                            ),
                        )
                    )
                )

        return produce

    def _r2_producer(
        self, specialist: Specialist, claim: ClaimDetail, verdicts: dict[str, SpecialistVerdict]
    ) -> _Producer:
        peers = {
            aid: v.model_dump(mode="json")
            for aid, v in verdicts.items()
            if aid != specialist.id
        }
        peers_json = json.dumps(peers, ensure_ascii=False, default=str)

        async def produce(queue: asyncio.Queue[Any]) -> None:
            try:
                system = self._prompts.load(specialist.prompt_id, "v1")
                await self._stream_tokens(
                    queue,
                    agent_id=specialist.id,
                    round_num=2,
                    system=system,
                    user=(
                        f"[especialista:{specialist.id}] [fase:narracion]\n"
                        f"Tus colegas dieron estos veredictos:\n{peers_json}\n\n"
                        f"Reacciona en 1-2 frases: ¿mantienes o ajustas tu postura?"
                    ),
                )
                rebuttal = await self._structured(
                    system=system,
                    user=(
                        f"[especialista:{specialist.id}] [fase:replica]\n"
                        f"Veredictos de tus colegas:\n{peers_json}\n\n"
                        f"Emite tu RÉPLICA estructurada."
                    ),
                    schema=SpecialistRebuttal,
                )
                await queue.put(
                    AgentRebuttalEvent(
                        data=AgentRebuttalData(agent_id=specialist.id, rebuttal=rebuttal)
                    )
                )
            except Exception as exc:
                logger.exception("panel R2 specialist %s failed", specialist.id)
                await queue.put(
                    PanelErrorEvent(
                        data=PanelErrorData(
                            agent_id=specialist.id,
                            code="specialist_r2_error",
                            message=str(exc),
                        )
                    )
                )
                await queue.put(
                    AgentRebuttalEvent(
                        data=AgentRebuttalData(
                            agent_id=specialist.id,
                            rebuttal=SpecialistRebuttal(
                                ajuste="sin réplica (falló)",
                                nivel_actualizado=claim.nivel,
                                cambia_postura=False,
                            ),
                        )
                    )
                )

        return produce

    async def _moderator(
        self,
        claim: ClaimDetail,
        verdicts: dict[str, SpecialistVerdict],
        rebuttals: dict[str, SpecialistRebuttal],
    ) -> AsyncGenerator[PanelStreamEvent, None]:
        try:
            system = self._prompts.load(MODERATOR_PROMPT_ID, "v1")
            payload = {
                # Deterministic engine verdict — the panel's job is to corroborate
                # or challenge it (divergence = the key decision signal).
                "motor": {"score": claim.score, "nivel": claim.nivel.value},
                "veredictos": {k: v.model_dump(mode="json") for k, v in verdicts.items()},
                "replicas": {k: r.model_dump(mode="json") for k, r in rebuttals.items()},
            }
            payload_json = json.dumps(payload, ensure_ascii=False, default=str)
            user_narr = (
                "[fase:narracion-moderador]\n"
                f"Sintetiza el debate del panel en 2-3 frases.\n\n{payload_json}"
            )
            messages = [
                Message(role="system", content=system),
                Message(role="user", content=user_narr),
            ]
            async for llm_event in self._llm.stream(messages, model=self._model):
                if llm_event.type == "token":
                    delta = str(llm_event.data.get("delta", ""))
                    if delta:
                        yield ModeratorTokenEvent(data=ModeratorTokenData(delta=delta))
            consensus = await self._structured(
                system=system,
                user=(
                    "[fase:consenso]\n"
                    f"Emite el CONSENSO estructurado del panel.\n\n{payload_json}"
                ),
                schema=PanelConsensus,
            )
            yield ConsensusEvent(data=ConsensusData(consensus=consensus))
        except Exception as exc:
            logger.exception("panel moderator failed")
            yield PanelErrorEvent(data=PanelErrorData(code="moderator_error", message=str(exc)))

    # ----- llm helpers ---------------------------------------------------

    async def _stream_tokens(
        self, queue: asyncio.Queue[Any], *, agent_id: str, round_num: int, system: str, user: str
    ) -> None:
        messages = [Message(role="system", content=system), Message(role="user", content=user)]
        async for llm_event in self._llm.stream(messages, model=self._model):
            if llm_event.type == "token":
                delta = str(llm_event.data.get("delta", ""))
                if delta:
                    await queue.put(
                        AgentTokenEvent(
                            data=AgentTokenData(
                                agent_id=agent_id, round=round_num, delta=delta
                            )
                        )
                    )

    async def _structured(self, *, system: str, user: str, schema: type[_M]) -> _M:
        result = await self._llm.complete(
            messages=[Message(role="system", content=system), Message(role="user", content=user)],
            model=self._model,
            response_format=ResponseFormat(
                schema_name=schema.__name__, json_schema=schema.model_json_schema(), strict=True
            ),
        )
        return schema.model_validate_json(result.message.content)

    async def _drain(self, producers: list[_Producer]) -> AsyncGenerator[PanelStreamEvent, None]:
        """Run producers concurrently, yielding their queued events as they arrive."""
        queue: asyncio.Queue[Any] = asyncio.Queue()

        async def run_one(producer: _Producer) -> None:
            try:
                await producer(queue)
            finally:
                await queue.put(_SENTINEL)

        tasks = [asyncio.create_task(run_one(p)) for p in producers]
        remaining = len(tasks)
        try:
            while remaining:
                item = await queue.get()
                if item is _SENTINEL:
                    remaining -= 1
                    continue
                yield item
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
