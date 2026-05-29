"""reconcile_consensus forces the panel verdict to agree with the motor's facts."""

from __future__ import annotations

from app.schemas.panel import PanelConsensus, SpecialistRebuttal, SpecialistVerdict
from app.schemas.risk import Tier
from app.use_cases.analyze_panel import reconcile_consensus
from tests.fixtures.claims import claim_amarillo, claim_rojo


def _verdict(nivel: Tier) -> SpecialistVerdict:
    return SpecialistVerdict(nivel=nivel, dictamen="posible caso para revisión")


def _rebuttal(nivel: Tier) -> SpecialistRebuttal:
    return SpecialistRebuttal(ajuste="mantengo", nivel_actualizado=nivel, cambia_postura=False)


def _consensus(nivel: Tier, *, falso_positivo: bool, acuerdo: float = 0.5) -> PanelConsensus:
    return PanelConsensus(
        nivel_final=nivel,
        nivel_de_acuerdo=acuerdo,
        resumen="El panel confirma este nivel.",
        accion_recomendada="Escalar a la Unidad Antifraude.",
        posible_falso_positivo=falso_positivo,
    )


def test_hard_rule_rojo_can_never_be_false_positive() -> None:
    # SIN-0160-style: motor ROJO via RF-01/RF-06; panel down-weights to amarillo
    # and the LLM stamped posible_falso_positivo=True. The hard rule must win.
    claim = claim_rojo()  # nivel rojo, alertas include RF-01 + RF-06
    verdicts = {f"a{i}": _verdict(Tier.amarillo) for i in range(4)}
    rebuttals = {f"a{i}": _rebuttal(Tier.amarillo) for i in range(4)}
    out = reconcile_consensus(
        _consensus(Tier.amarillo, falso_positivo=True), claim, verdicts, rebuttals
    )
    assert out.posible_falso_positivo is False


def test_agreement_is_recomputed_from_votes() -> None:
    claim = claim_rojo()
    # 2 of 4 final levels match the consensus (rojo) -> 0.5.
    levels = [Tier.rojo, Tier.rojo, Tier.amarillo, Tier.verde]
    verdicts = {str(i): _verdict(lvl) for i, lvl in enumerate(levels)}
    rebuttals = {str(i): _rebuttal(lvl) for i, lvl in enumerate(levels)}
    out = reconcile_consensus(
        _consensus(Tier.rojo, falso_positivo=False, acuerdo=0.9), claim, verdicts, rebuttals
    )
    assert out.nivel_de_acuerdo == 0.5


def test_rebuttal_level_overrides_r1_vote_for_agreement() -> None:
    claim = claim_rojo()
    # R1 says amarillo but the réplica moved to rojo — agreement uses the réplica.
    verdicts = {"a": _verdict(Tier.amarillo)}
    rebuttals = {"a": _rebuttal(Tier.rojo)}
    out = reconcile_consensus(
        _consensus(Tier.rojo, falso_positivo=False), claim, verdicts, rebuttals
    )
    assert out.nivel_de_acuerdo == 1.0


def test_below_motor_no_hard_rule_keeps_false_positive() -> None:
    # Genuine over-mark case: motor amarillo (only FS rules), panel drops to verde.
    claim = claim_amarillo()  # nivel amarillo, no RF-* alerts
    verdicts = {f"a{i}": _verdict(Tier.verde) for i in range(4)}
    rebuttals = {f"a{i}": _rebuttal(Tier.verde) for i in range(4)}
    out = reconcile_consensus(
        _consensus(Tier.verde, falso_positivo=True), claim, verdicts, rebuttals
    )
    assert out.posible_falso_positivo is True


def test_confirming_motor_is_not_a_false_positive() -> None:
    # Panel confirms the motor level (not below) -> FP suppressed even without a hard rule.
    claim = claim_amarillo()
    verdicts = {f"a{i}": _verdict(Tier.amarillo) for i in range(4)}
    rebuttals = {f"a{i}": _rebuttal(Tier.amarillo) for i in range(4)}
    out = reconcile_consensus(
        _consensus(Tier.amarillo, falso_positivo=True), claim, verdicts, rebuttals
    )
    assert out.posible_falso_positivo is False
