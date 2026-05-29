"""Unit tests for FS-08 ramo-aware extension.

Verifies that the ramo-specific required-doc sets fire correctly and that the
backward-compat generic path is unchanged.
"""

from datetime import date

import pytest

from app.domain.rules.context import RuleContext
from app.domain.rules.signals.FS_08_incomplete_documents import FS08IncompleteDocuments
from app.schemas.claim import ClaimDetail, ClaimDocument, ClaimReview
from app.schemas.risk import Tier
from tests.fixtures.claims import claim_verde


@pytest.fixture()
def rule() -> FS08IncompleteDocuments:
    return FS08IncompleteDocuments()


def _salud_claim(docs: list[ClaimDocument]) -> ClaimDetail:
    """Minimal Salud claim with the provided document list."""
    return ClaimDetail(
        id="SIN-FS08-S",
        ramo="Salud",
        cobertura="Hospitalización",
        asegurado="T. Ramos",
        asegurado_id="ASE-2001",
        poliza="POL-6001",
        ciudad="Quito",
        fecha_ocurrencia=date(2026, 3, 1),
        fecha_reporte=date(2026, 3, 5),
        monto_reclamado=3000.0,
        suma_asegurada=50000.0,
        estado="Reserva",
        sucursal="Quito Norte",
        descripcion="Hospitalización por complicaciones médicas.",
        score=10,
        nivel=Tier.verde,
        documentos=docs,
        review=ClaimReview(),
    )


def _vehiculos_claim(docs: list[ClaimDocument]) -> ClaimDetail:
    return ClaimDetail(
        id="SIN-FS08-V",
        ramo="Vehículos",
        cobertura="Pérdida Parcial",
        asegurado="A. García",
        asegurado_id="ASE-2002",
        poliza="POL-6002",
        ciudad="Guayaquil",
        fecha_ocurrencia=date(2026, 3, 1),
        fecha_reporte=date(2026, 3, 3),
        monto_reclamado=5000.0,
        suma_asegurada=20000.0,
        estado="Reserva",
        sucursal="Guayaquil Centro",
        descripcion="Colisión en vía urbana.",
        score=10,
        nivel=Tier.verde,
        documentos=docs,
        review=ClaimReview(),
    )


class TestFS08SaludRamoAware:
    def test_salud_missing_historia_clinica_fires(self, rule: FS08IncompleteDocuments) -> None:
        """Salud claim without 'Historia clínica' must fire FS-08."""
        docs = [
            ClaimDocument(tipo="Cédula", estado="Entregado"),
            ClaimDocument(tipo="Orden médica", estado="Entregado"),
            # Historia clínica is missing
        ]
        claim = _salud_claim(docs)
        ctx = RuleContext.from_claim(claim)
        result = rule.evaluate(claim, ctx)
        assert result is not None
        assert result.code == "FS-08"
        assert "Historia clínica" in result.evidence["documentos_faltantes"]
        assert result.evidence["ramo"] == "Salud"

    def test_salud_complete_does_not_fire(self, rule: FS08IncompleteDocuments) -> None:
        """Salud claim with all required docs present must NOT fire."""
        docs = [
            ClaimDocument(tipo="Cédula", estado="Entregado"),
            ClaimDocument(tipo="Historia clínica", estado="Entregado"),
            ClaimDocument(tipo="Orden médica", estado="Entregado"),
        ]
        claim = _salud_claim(docs)
        ctx = RuleContext.from_claim(claim)
        assert rule.evaluate(claim, ctx) is None


class TestFS08VehiculosRamoAware:
    def test_vehiculos_complete_does_not_fire(self, rule: FS08IncompleteDocuments) -> None:
        """Vehículos claim with all required docs present must NOT fire."""
        docs = [
            ClaimDocument(tipo="Cédula de identidad", estado="Entregado"),
            ClaimDocument(tipo="Matrícula del vehículo", estado="Entregado"),
            ClaimDocument(tipo="Parte policial", estado="Entregado"),
        ]
        claim = _vehiculos_claim(docs)
        ctx = RuleContext.from_claim(claim)
        # documentos_incompletos=False because falta=False on all docs
        assert rule.evaluate(claim, ctx) is None

    def test_vehiculos_missing_matricula_fires(self, rule: FS08IncompleteDocuments) -> None:
        docs = [
            ClaimDocument(tipo="Cédula", estado="Entregado"),
            ClaimDocument(tipo="Parte policial", estado="Entregado"),
            # Matrícula absent
        ]
        claim = _vehiculos_claim(docs)
        ctx = RuleContext.from_claim(claim)
        result = rule.evaluate(claim, ctx)
        assert result is not None
        assert "Matrícula" in result.evidence["documentos_faltantes"]


class TestFS08GenericFallback:
    def test_unknown_ramo_uses_generic(self, rule: FS08IncompleteDocuments) -> None:
        """A ramo not in the map falls back to ctx.documentos_incompletos."""
        # claim_verde = Vehículos but we override ramo to something unknown
        # and set falta=True on one doc to trigger ctx.documentos_incompletos
        claim = claim_verde()
        # Inject a missing doc into the fixture
        claim.documentos = [ClaimDocument(tipo="Denuncia", estado="Pendiente", falta=True)]
        ctx = RuleContext.from_claim(claim)
        # Override ramo so it won't match any configured set
        claim.ramo = "Embarcaciones"
        # ctx.documentos_incompletos was already set from falta=True
        assert ctx.documentos_incompletos is True
        result = rule.evaluate(claim, ctx)
        assert result is not None
        assert result.code == "FS-08"

    def test_unknown_ramo_complete_no_fire(self, rule: FS08IncompleteDocuments) -> None:
        claim = claim_verde()  # all docs present (falta=False)
        claim.ramo = "Embarcaciones"
        ctx = RuleContext.from_claim(claim)
        assert ctx.documentos_incompletos is False
        assert rule.evaluate(claim, ctx) is None
