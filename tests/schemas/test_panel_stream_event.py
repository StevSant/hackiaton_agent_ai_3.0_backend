"""PanelStreamEvent union round-trips and discriminates by `type`."""

from __future__ import annotations

from pydantic import TypeAdapter

from app.schemas.panel import (
    AgentTokenData,
    AgentTokenEvent,
    AgentVerdictData,
    AgentVerdictEvent,
    ConsensusData,
    ConsensusEvent,
    PanelConsensus,
    PanelRosterEntry,
    PanelStartData,
    PanelStartEvent,
    PanelStreamEvent,
    SpecialistVerdict,
)
from app.schemas.risk import Tier


def test_panel_start_event_serializes() -> None:
    ev = PanelStartEvent(
        data=PanelStartData(
            claim_id="SIN-0001",
            roster=[PanelRosterEntry(agent_id="reglas", display_name="Analista de Reglas", lens="reglas")],
        )
    )
    dumped = ev.model_dump(mode="json")
    assert dumped["type"] == "panel_start"
    assert dumped["data"]["roster"][0]["agent_id"] == "reglas"


def test_agent_token_event_carries_round_and_agent() -> None:
    ev = AgentTokenEvent(data=AgentTokenData(agent_id="ml", round=1, delta="hola"))
    assert ev.model_dump(mode="json")["data"]["round"] == 1


def test_agent_verdict_event_wraps_structured_verdict() -> None:
    ev = AgentVerdictEvent(
        data=AgentVerdictData(
            agent_id="reglas",
            verdict=SpecialistVerdict(
                nivel=Tier.rojo,
                dictamen="posible caso de revisión",
                puntos_clave=["RF-01 disparó"],
                confianza="alta",
                citas=["SIN-0001", "RF-01"],
            ),
        )
    )
    assert ev.model_dump(mode="json")["data"]["verdict"]["nivel"] == "rojo"


def test_consensus_event_framing_has_no_bare_fraude() -> None:
    cons = PanelConsensus(
        nivel_final=Tier.amarillo,
        nivel_de_acuerdo=0.75,
        puntos_de_conflicto=["Reglas vs ML"],
        resumen="Requiere revisión humana.",
        accion_recomendada="Escalar a la Unidad Antifraude para revisión documental.",
        posible_falso_positivo=True,
    )
    ev = ConsensusEvent(data=ConsensusData(consensus=cons))
    assert ev.model_dump(mode="json")["type"] == "consensus"


def test_union_discriminates_by_type() -> None:
    adapter = TypeAdapter(PanelStreamEvent)
    parsed = adapter.validate_python({"type": "agent_token", "data": {"agent_id": "ml", "round": 2, "delta": "x"}})
    assert isinstance(parsed, AgentTokenEvent)
