"""Tests for F4 — GET /api/v1/claims/{id}/report.docx

Strategy: override get_current_user, get_claim_queries_dep, get_reviews_store,
and the generate_claim_report_docx / get_claim_detail use cases so no real DB
or OpenAI call is needed.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
import pytest

from app.api.deps import get_claim_queries_dep, get_current_user, get_reviews_store
from app.domain.auth.role import Role
from app.domain.auth.user import User
from app.main import create_app
from app.schemas.claim import ClaimDetail, ClaimReview
from app.schemas.narrative_analysis import ExtractedEntities, NarrativeAnalysis
from app.schemas.panel import (
    PanelAnalysis,
    PanelConsensus,
    PanelLaneSnapshot,
    SpecialistVerdict,
)
from app.schemas.risk import FactorContribution, SimilarClaim, Tier

_KNOWN_CLAIM_ID = "SIN-DOCX-001"
_UNKNOWN_CLAIM_ID = "SIN-MISSING-999"

_DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def _stub_user() -> User:
    return User(
        id=uuid.uuid5(uuid.NAMESPACE_URL, "analista@test.local"),
        email="analista@test.local",
        role=Role.analista,
        full_name="Test Analista",
    )


def _make_claim_detail() -> ClaimDetail:
    return ClaimDetail(
        id=_KNOWN_CLAIM_ID,
        ramo="Vehículos",
        cobertura="Responsabilidad Civil",
        asegurado="Test Asegurado",
        asegurado_id="ASE-TEST-001",
        poliza="POL-TEST-001",
        ciudad="Guayaquil",
        fecha_ocurrencia="2026-04-10",  # type: ignore[arg-type]
        fecha_reporte="2026-04-12",  # type: ignore[arg-type]
        monto_reclamado=1500.0,
        suma_asegurada=20000.0,
        estado="Reserva",
        sucursal="Guayaquil Centro",
        descripcion="Choque leve en semáforo.",
        score=15,
        nivel=Tier.verde,
        review=ClaimReview(),
    )


@pytest.mark.asyncio
async def test_download_report_docx_returns_200_and_correct_content_type() -> None:
    """GET /claims/{id}/report.docx returns 200 + docx content-type + non-empty body."""
    import app.api.v1.claims as _claims_module

    # Patch get_claim_detail and generate_claim_report_docx at module level
    async def _fake_get_detail(
        queries: Any,
        claim_id: str,
        *,
        reviews_store: Any = None,
        classifier: Any = None,
        detector: Any = None,
        similarity: Any = None,
    ) -> ClaimDetail | None:
        if claim_id == _KNOWN_CLAIM_ID:
            return _make_claim_detail()
        return None

    async def _fake_generate_docx(claim: ClaimDetail) -> bytes:
        # Minimal fake docx bytes — enough to test the endpoint contract
        return b"PK\x03\x04fake-docx-content"

    orig_get = _claims_module.get_claim_detail
    orig_gen = _claims_module.generate_claim_report_docx

    _claims_module.get_claim_detail = _fake_get_detail  # type: ignore[assignment]
    _claims_module.generate_claim_report_docx = _fake_generate_docx  # type: ignore[assignment]

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user
    app.dependency_overrides[get_claim_queries_dep] = lambda: object()
    app.dependency_overrides[get_reviews_store] = lambda: object()

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/v1/claims/{_KNOWN_CLAIM_ID}/report.docx")
    finally:
        _claims_module.get_claim_detail = orig_get  # type: ignore[assignment]
        _claims_module.generate_claim_report_docx = orig_gen  # type: ignore[assignment]

    assert response.status_code == 200, response.text
    assert _DOCX_CONTENT_TYPE in response.headers.get("content-type", "")
    assert len(response.content) > 0
    assert f"reporte-{_KNOWN_CLAIM_ID}.docx" in response.headers.get(
        "content-disposition", ""
    )


@pytest.mark.asyncio
async def test_report_docx_includes_analysis_sections() -> None:
    """The generated docx surfaces ML, anomaly, NLP and panel analysis text."""
    from io import BytesIO

    from docx import Document

    from app.use_cases.generate_claim_report_docx import generate_claim_report_docx

    claim = _make_claim_detail()
    claim.ml_factors = [
        FactorContribution(feature="monto_reclamado", shap_value=0.42, direction="up"),
    ]
    claim.anomaly_score = -0.31
    claim.nearest_normal_claim_id = "SIN-NORMAL-007"
    claim.similar = [
        SimilarClaim(claim_id="SIN-SIM-002", similarity=0.91, snippet="Choque similar."),
    ]
    claim.narrative_analysis = NarrativeAnalysis(
        entidades=ExtractedEntities(personas=["Juan Pérez"], lugares=["Av. 9 de Octubre"]),
        narrativa_ilogica=True,
        incoherencias=["La hora del parte no coincide con el relato."],
        resumen_narrativa="El asegurado relata un choque leve en un semáforo.",
    )
    claim.panel_analysis = PanelAnalysis(
        lanes=[
            PanelLaneSnapshot(
                agent_id="doc",
                display_name="Especialista Documental",
                lens="documentos",
                verdict=SpecialistVerdict(
                    nivel=Tier.amarillo,
                    dictamen="Requiere revisión de documentos.",
                    puntos_clave=["Falta el parte policial."],
                ),
            ),
        ],
        moderator_text="Los especialistas coinciden en revisar documentos.",
        consensus=PanelConsensus(
            nivel_final=Tier.amarillo,
            nivel_de_acuerdo=0.8,
            puntos_de_conflicto=["Discrepan en la urgencia."],
            resumen="El caso amerita revisión documental.",
            accion_recomendada="Escalar a la Unidad Antifraude para revisión de documentos.",
        ),
        generated_at="2026-04-12T10:00:00Z",  # type: ignore[arg-type]
    )

    docx_bytes = await generate_claim_report_docx(claim)
    text = "\n".join(p.text for p in Document(BytesIO(docx_bytes)).paragraphs)

    assert "Factores del modelo (SHAP)" in text
    assert "monto_reclamado" in text
    assert "Indicador de anomalía" in text
    assert "SIN-NORMAL-007" in text
    assert "Narrativas similares" in text
    assert "SIN-SIM-002" in text
    assert "Análisis NLP del relato" in text
    assert "El asegurado relata un choque leve" in text
    assert "La hora del parte no coincide con el relato." in text
    assert "Panel multi-agente" in text
    assert "Especialista Documental" in text
    assert "Escalar a la Unidad Antifraude para revisión de documentos." in text


@pytest.mark.asyncio
async def test_download_report_docx_unknown_claim_returns_404() -> None:
    """GET /claims/{id}/report.docx returns 404 when the claim is not found."""
    import app.api.v1.claims as _claims_module

    async def _fake_get_detail(
        queries: Any,
        claim_id: str,
        *,
        reviews_store: Any = None,
        classifier: Any = None,
        detector: Any = None,
        similarity: Any = None,
    ) -> ClaimDetail | None:
        return None  # always not found

    orig_get = _claims_module.get_claim_detail
    _claims_module.get_claim_detail = _fake_get_detail  # type: ignore[assignment]

    app = create_app()
    app.dependency_overrides[get_current_user] = _stub_user
    app.dependency_overrides[get_claim_queries_dep] = lambda: object()
    app.dependency_overrides[get_reviews_store] = lambda: object()

    try:
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    f"/api/v1/claims/{_UNKNOWN_CLAIM_ID}/report.docx"
                )
    finally:
        _claims_module.get_claim_detail = orig_get  # type: ignore[assignment]

    assert response.status_code == 404, response.text
