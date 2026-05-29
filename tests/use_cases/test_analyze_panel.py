"""AnalyzePanel emits the full event sequence with a scripted fake LLM."""

from __future__ import annotations

from typing import Any

import pytest

from app.agents.fraud_panel import PANEL_ROSTER
from app.infrastructure.llm import InMemoryFakeLLM, PromptLoader
from app.use_cases.analyze_panel import AnalyzePanel
from app.use_cases.claim_queries import InMemoryClaimQueries
from tests.fixtures.claims import claim_rojo

from pathlib import Path


def _prompts() -> PromptLoader:
    base = Path(__file__).resolve().parents[1] / ".." / "app" / "agents" / "fraud_panel" / "prompts"
    return PromptLoader(base_dir=base.resolve())


def _script() -> dict[str, Any]:
    # Keyed by the phase tags AnalyzePanel injects into each user payload:
    #   "[especialista:{id}] [fase:veredicto]" -> SpecialistVerdict dict
    #   "[especialista:{id}] [fase:replica]"   -> SpecialistRebuttal dict
    #   "[fase:consenso]"                       -> PanelConsensus dict
    script: dict[str, Any] = {}
    for s in PANEL_ROSTER:
        script[f"[especialista:{s.id}] [fase:veredicto]"] = {
            "nivel": "rojo" if s.id == "reglas" else "amarillo",
            "dictamen": "posible caso para revisión",
            "puntos_clave": [f"lente {s.id}"],
            "confianza": "media",
            "citas": ["SIN-0003"],
        }
        script[f"[especialista:{s.id}] [fase:replica]"] = {
            "ajuste": "mantengo mi postura",
            "nivel_actualizado": "amarillo",
            "cambia_postura": False,
        }
    script["[fase:consenso]"] = {
        "nivel_final": "amarillo",
        "nivel_de_acuerdo": 0.75,
        "puntos_de_conflicto": ["Reglas (rojo) vs resto (amarillo)"],
        "resumen": "El caso requiere revisión humana.",
        "accion_recomendada": "Escalar a la Unidad Antifraude para revisión documental.",
        "posible_falso_positivo": False,
    }
    return script


@pytest.mark.asyncio
async def test_panel_emits_full_sequence() -> None:
    llm = InMemoryFakeLLM(script=_script())
    queries = InMemoryClaimQueries(claims=[claim_rojo()])
    panel = AnalyzePanel(llm=llm, prompts=_prompts(), queries=queries, model="gpt-4o-mini")

    events = [ev async for ev in panel.run("SIN-0003")]
    types = [e.type for e in events]

    assert types[0] == "panel_start"
    assert types[-1] == "done"
    assert types.count("agent_verdict") == 4
    assert types.count("agent_rebuttal") == 4
    assert types.count("consensus") == 1
    assert "agent_token" in types  # streamed narration happened
    assert "error" not in types

    last_verdict_idx = max(i for i, t in enumerate(types) if t == "agent_verdict")
    first_rebuttal_idx = min(i for i, t in enumerate(types) if t == "agent_rebuttal")
    assert last_verdict_idx < first_rebuttal_idx


@pytest.mark.asyncio
async def test_panel_missing_claim_emits_error_then_done() -> None:
    llm = InMemoryFakeLLM(script=_script())
    queries = InMemoryClaimQueries(claims=[claim_rojo()])
    panel = AnalyzePanel(llm=llm, prompts=_prompts(), queries=queries, model="gpt-4o-mini")

    events = [ev async for ev in panel.run("SIN-NOPE")]
    types = [e.type for e in events]
    assert types == ["error", "done"]
