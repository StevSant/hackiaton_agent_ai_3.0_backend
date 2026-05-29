"""Stream a panel run and persist the completed debate.

Wraps ``AnalyzePanel.run`` — yields every event unchanged (so the SSE route stays
thin) while accumulating lane/consensus state, then caches a ``PanelAnalysis`` on
the claim once the stream completes. Persistence failures never break the stream.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth.user import User
from app.infrastructure.audit import AuditStore
from app.schemas.audit import AuditAction, AuditActor
from app.schemas.panel import (
    AgentRebuttalEvent,
    AgentTokenEvent,
    AgentVerdictEvent,
    ConsensusEvent,
    ModeratorTokenEvent,
    PanelAnalysis,
    PanelErrorEvent,
    PanelLaneSnapshot,
    PanelStartEvent,
    PanelStreamEvent,
)
from app.use_cases.analyze_panel.analyze_panel import AnalyzePanel
from app.use_cases.analyze_panel.save_panel_analysis import save_panel_analysis
from app.use_cases.emit_audit_event import emit_audit_event

logger = logging.getLogger(__name__)


async def run_and_persist(
    panel: AnalyzePanel,
    session: AsyncSession,
    claim_id: str,
    *,
    audit: AuditStore | None = None,
    user: User | None = None,
) -> AsyncGenerator[PanelStreamEvent, None]:
    lanes: dict[str, PanelLaneSnapshot] = {}
    order: list[str] = []
    moderator_text = ""
    consensus = None
    saw_consensus = False

    # `session` (from the route's get_session) is eagerly connected but we don't
    # touch it until save_panel_analysis at the very end. Hand its pooled
    # connection back before the long, DB-free LLM debate; SQLAlchemy re-acquires
    # lazily when we persist. Best-effort — the debate must run regardless.
    try:
        await session.rollback()
    except Exception:  # pragma: no cover - releasing an idle connection
        logger.debug("panel: could not pre-release persist session", exc_info=True)

    async for event in panel.run(claim_id):
        if isinstance(event, PanelStartEvent):
            for entry in event.data.roster:
                lanes[entry.agent_id] = PanelLaneSnapshot(
                    agent_id=entry.agent_id,
                    display_name=entry.display_name,
                    lens=entry.lens,
                )
                order.append(entry.agent_id)
        elif isinstance(event, AgentTokenEvent):
            lane = lanes.get(event.data.agent_id)
            if lane is not None:
                if event.data.round == 1:
                    lane.narracion += event.data.delta
                else:
                    lane.rebuttal_narracion += event.data.delta
        elif isinstance(event, AgentVerdictEvent):
            lane = lanes.get(event.data.agent_id)
            if lane is not None:
                lane.verdict = event.data.verdict
        elif isinstance(event, AgentRebuttalEvent):
            lane = lanes.get(event.data.agent_id)
            if lane is not None:
                lane.rebuttal = event.data.rebuttal
        elif isinstance(event, ModeratorTokenEvent):
            moderator_text += event.data.delta
        elif isinstance(event, ConsensusEvent):
            consensus = event.data.consensus
            saw_consensus = True
        elif isinstance(event, PanelErrorEvent):
            # A specialist's R1 failure (no real opinion). R2 failures keep the
            # good R1 verdict, so only the R1 error flags the whole lane.
            if event.data.agent_id and event.data.code == "specialist_error":
                lane = lanes.get(event.data.agent_id)
                if lane is not None:
                    lane.failed = True

        yield event

    if not saw_consensus and not lanes:
        return  # claim not found / fetch error — nothing worth caching

    analysis = PanelAnalysis(
        lanes=[lanes[aid] for aid in order],
        moderator_text=moderator_text,
        consensus=consensus,
        generated_at=datetime.now(tz=UTC),
    )
    try:
        await save_panel_analysis(session, claim_id, analysis)
    except Exception:  # persistence is best-effort — never break the stream
        logger.exception("panel: failed to persist analysis for %s", claim_id)

    # Audit the run once it produced a real consensus — best-effort, never breaks
    # the stream. Actor is the agente (the AI panel did the analysis), stamped
    # with the human who triggered it.
    if audit is not None and user is not None and consensus is not None:
        acuerdo_pct = round(consensus.nivel_de_acuerdo * 100)
        falso_positivo = (
            " · posible falso positivo" if consensus.posible_falso_positivo else ""
        )
        try:
            await emit_audit_event(
                audit,
                user=user,
                action=AuditAction.analisis_consenso,
                actor=AuditActor.agente,
                title="Ejecutó análisis multi-agente",
                detail=(
                    f"Consenso {consensus.nivel_final.value} · "
                    f"acuerdo {acuerdo_pct}%{falso_positivo}"
                ),
                target=claim_id,
            )
        except Exception:  # auditing is best-effort — never break the stream
            logger.exception("panel: failed to audit analysis for %s", claim_id)
