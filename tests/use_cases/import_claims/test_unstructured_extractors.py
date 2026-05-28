"""Tests for PDF and Word unstructured document extractors.

Uses InMemoryFakeLLM to avoid real LLM calls. The fake is configured with a
scripted JSON response matching what the LLM would extract from each sample document.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from app.infrastructure.llm.fake_llm import InMemoryFakeLLM
from app.use_cases.import_claims._pdf_extractor import parse_pdf
from app.use_cases.import_claims._docx_extractor import parse_docx

_SAMPLES_PDF = Path(__file__).parent.parent.parent.parent / "data" / "casos_demo" / "pdf"
_SAMPLES_DOCX = Path(__file__).parent.parent.parent.parent / "data" / "casos_demo" / "docx"


# ---------------------------------------------------------------------------
# Shared fake LLM factory
# ---------------------------------------------------------------------------

def _make_llm(extracted: dict) -> InMemoryFakeLLM:
    """Return a fake LLM that will always respond with the given extracted dict."""
    fake = InMemoryFakeLLM(
        script={
            "analiza el siguiente": extracted,
        }
    )
    return fake


# ---------------------------------------------------------------------------
# PDF tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_pdf_robo_001_extracts_claim() -> None:
    """PDF 001: denuncia_policial_robo_001.pdf → ClaimDetail with correct fields."""
    pdf_bytes = (_SAMPLES_PDF / "denuncia_policial_robo_001.pdf").read_bytes()
    extracted = {
        "id": "SIN-DEMO-001",
        "cobertura": "Pérdida Total por Robo",
        "asegurado": "Andrés Felipe Cordero Naranjo",
        "asegurado_id": "ASG-D0001",
        "poliza": "PV-DEMO-0001",
        "ciudad": "Quito",
        "fecha_ocurrencia": "2026-05-01",
        "fecha_reporte": "2026-05-08",
        "monto_reclamado": 41160.0,
        "suma_asegurada": 42000.0,
        "descripcion": "Robo de Toyota Hilux 2023, placas PCH-4821, en Cumbayá, Quito.",
        "vehiculo_marca": "Toyota",
        "vehiculo_modelo": "Hilux",
        "vehiculo_anio": 2023,
        "vehiculo_placa": "PCH-4821",
        "vehiculo_chasis": "MR0HZ8CD400123456",
    }
    llm = _make_llm(extracted)

    claims = await parse_pdf(pdf_bytes, llm=llm)

    assert len(claims) == 1
    claim = claims[0]
    assert claim.id == "SIN-DEMO-001"
    assert claim.cobertura == "Pérdida Total por Robo"
    assert claim.asegurado == "Andrés Felipe Cordero Naranjo"
    assert claim.ciudad == "Quito"
    assert claim.monto_reclamado == 41160.0
    assert claim.vehiculo is not None
    assert claim.vehiculo.marca == "Toyota"
    assert claim.vehiculo.placa == "PCH-4821"
    # Dates
    from datetime import date
    assert claim.fecha_ocurrencia == date(2026, 5, 1)
    assert claim.fecha_reporte == date(2026, 5, 8)
    # Safe defaults
    assert claim.ramo == "Vehículos"
    assert claim.estado == "Reserva"
    assert claim.score == 0


@pytest.mark.asyncio
async def test_parse_pdf_pericial_002_extracts_claim() -> None:
    """PDF 002: informe_pericial_002.pdf → Chevrolet Aveo case."""
    pdf_bytes = (_SAMPLES_PDF / "informe_pericial_002.pdf").read_bytes()
    extracted = {
        "id": "SIN-DEMO-002",
        "cobertura": "Daños Materiales",
        "asegurado": "Patricia Lorena Vásquez Montoya",
        "asegurado_id": "ASG-D0002",
        "poliza": "PV-DEMO-0002",
        "ciudad": "Guayaquil",
        "fecha_ocurrencia": "2026-05-11",
        "fecha_reporte": "2026-05-12",
        "monto_reclamado": 8400.0,
        "suma_asegurada": 14000.0,
        "descripcion": "Colisión trasera de Chevrolet Aveo 2020 en Av. Francisco de Orellana, Guayaquil.",
        "vehiculo_marca": "Chevrolet",
        "vehiculo_modelo": "Aveo",
        "vehiculo_anio": 2020,
        "vehiculo_placa": "GBR-2294",
        "vehiculo_chasis": "8LBTZS5E9LG041872",
    }
    llm = _make_llm(extracted)

    claims = await parse_pdf(pdf_bytes, llm=llm)

    assert len(claims) == 1
    claim = claims[0]
    assert claim.cobertura == "Daños Materiales"
    assert claim.asegurado == "Patricia Lorena Vásquez Montoya"
    assert claim.ciudad == "Guayaquil"
    assert claim.monto_reclamado == 8400.0
    assert claim.vehiculo is not None
    assert claim.vehiculo.marca == "Chevrolet"


@pytest.mark.asyncio
async def test_parse_pdf_boleta_003_extracts_claim() -> None:
    """PDF 003: boleta_siniestro_003.pdf → Kia Picanto case with docs incompletos."""
    pdf_bytes = (_SAMPLES_PDF / "boleta_siniestro_003.pdf").read_bytes()
    extracted = {
        "id": "SIN-DEMO-003",
        "cobertura": "Daños",
        "asegurado": "Rodrigo Sebastián Arias Cifuentes",
        "asegurado_id": "ASG-D0003",
        "poliza": "PV-DEMO-0003",
        "ciudad": "Cuenca",
        "fecha_ocurrencia": "2026-04-15",
        "fecha_reporte": "2026-04-25",
        "monto_reclamado": 3200.0,
        "suma_asegurada": 8000.0,
        "descripcion": "Daños laterales en Kia Picanto 2019 en estacionamiento de Mall del Río, Cuenca.",
        "vehiculo_marca": "Kia",
        "vehiculo_modelo": "Picanto",
        "vehiculo_anio": 2019,
        "vehiculo_placa": "AZB-0571",
        "vehiculo_chasis": None,
    }
    llm = _make_llm(extracted)

    claims = await parse_pdf(pdf_bytes, llm=llm)

    assert len(claims) == 1
    claim = claims[0]
    assert claim.ciudad == "Cuenca"
    assert claim.sucursal == "Cuenca"  # no mapping → city name used
    assert claim.monto_reclamado == 3200.0


# ---------------------------------------------------------------------------
# DOCX tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_docx_perito_004_extracts_claim() -> None:
    """DOCX 004: informe_perito_004.docx → Hyundai Tucson raspón."""
    docx_bytes = (_SAMPLES_DOCX / "informe_perito_004.docx").read_bytes()
    extracted = {
        "id": "SIN-DEMO-004",
        "cobertura": "Daños Parciales",
        "asegurado": "Valeria Cristina Moreno Benítez",
        "asegurado_id": "ASG-D0004",
        "poliza": "PV-DEMO-0004",
        "ciudad": "Quito",
        "fecha_ocurrencia": "2026-04-20",
        "fecha_reporte": "2026-04-22",
        "monto_reclamado": 1200.0,
        "suma_asegurada": 28000.0,
        "descripcion": "Raspón superficial en Hyundai Tucson 2022 en estacionamiento Quicentro, Quito.",
        "vehiculo_marca": "Hyundai",
        "vehiculo_modelo": "Tucson",
        "vehiculo_anio": 2022,
        "vehiculo_placa": "PBD-1083",
        "vehiculo_chasis": None,
    }
    llm = _make_llm(extracted)

    claims = await parse_docx(docx_bytes, llm=llm)

    assert len(claims) == 1
    claim = claims[0]
    assert claim.cobertura == "Daños Parciales"
    assert claim.ciudad == "Quito"
    assert claim.monto_reclamado == 1200.0
    assert claim.vehiculo is not None
    assert claim.vehiculo.modelo == "Tucson"


@pytest.mark.asyncio
async def test_parse_docx_denuncia_005_extracts_claim() -> None:
    """DOCX 005: denuncia_005.docx → Mazda CX-5 daños totales."""
    docx_bytes = (_SAMPLES_DOCX / "denuncia_005.docx").read_bytes()
    extracted = {
        "id": "SIN-DEMO-005",
        "cobertura": "Daños Totales",
        "asegurado": "Jorge Mauricio Landívar Peñafiel",
        "asegurado_id": "ASG-D0005",
        "poliza": "PV-DEMO-0005",
        "ciudad": "Guayaquil",
        "fecha_ocurrencia": "2026-05-02",
        "fecha_reporte": "2026-05-12",
        "monto_reclamado": 22000.0,
        "suma_asegurada": 23000.0,
        "descripcion": "Daños severos en Mazda CX-5 2021 en sector industrial norte de Guayaquil.",
        "vehiculo_marca": "Mazda",
        "vehiculo_modelo": "CX-5",
        "vehiculo_anio": 2021,
        "vehiculo_placa": "GBT-9917",
        "vehiculo_chasis": None,
    }
    llm = _make_llm(extracted)

    claims = await parse_docx(docx_bytes, llm=llm)

    assert len(claims) == 1
    claim = claims[0]
    assert claim.cobertura == "Daños Totales"
    assert claim.monto_reclamado == 22000.0
    assert claim.vehiculo is not None
    assert claim.vehiculo.placa == "GBT-9917"


@pytest.mark.asyncio
async def test_parse_docx_robo_006_extracts_claim() -> None:
    """DOCX 006: denuncia_robo_006.docx → Toyota Hilux robo similar a caso_01."""
    docx_bytes = (_SAMPLES_DOCX / "denuncia_robo_006.docx").read_bytes()
    extracted = {
        "id": "SIN-DEMO-006",
        "cobertura": "Pérdida Total por Robo",
        "asegurado": "Carlos Vinicio Espinoza Maldonado",
        "asegurado_id": "ASG-D0006",
        "poliza": "PV-DEMO-0006",
        "ciudad": "Quito",
        "fecha_ocurrencia": "2026-05-12",
        "fecha_reporte": "2026-05-19",
        "monto_reclamado": 38500.0,
        "suma_asegurada": 40000.0,
        "descripcion": "Robo de Toyota Hilux 2022 en La Floresta, Quito. Denuncia fiscal presentada 7 días después.",
        "vehiculo_marca": "Toyota",
        "vehiculo_modelo": "Hilux",
        "vehiculo_anio": 2022,
        "vehiculo_placa": "GBC-7142",
        "vehiculo_chasis": "MR0HZ8CD0N0387251",
    }
    llm = _make_llm(extracted)

    claims = await parse_docx(docx_bytes, llm=llm)

    assert len(claims) == 1
    claim = claims[0]
    assert claim.cobertura == "Pérdida Total por Robo"
    assert claim.asegurado == "Carlos Vinicio Espinoza Maldonado"
    assert claim.vehiculo is not None
    assert claim.vehiculo.marca == "Toyota"
    assert claim.vehiculo.placa == "GBC-7142"


# ---------------------------------------------------------------------------
# Error / edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_pdf_random_bytes_raises() -> None:
    """Random bytes that are not a valid PDF raise ValueError."""
    bad_content = b"\x00\x01\x02\x03" * 50  # no PDF structure
    llm = InMemoryFakeLLM()
    with pytest.raises((ValueError, Exception)):
        await parse_pdf(bad_content, llm=llm)


@pytest.mark.asyncio
async def test_parse_pdf_blank_raises_value_error() -> None:
    """A minimal valid PDF with no extractable text raises ValueError."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Spacer
    from reportlab.lib.units import cm
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    doc.build([Spacer(1, 1 * cm)])  # blank page, no text
    blank_pdf = buf.getvalue()

    llm = InMemoryFakeLLM()
    with pytest.raises(ValueError, match="vacío|imágenes|texto suficiente"):
        await parse_pdf(blank_pdf, llm=llm)


@pytest.mark.asyncio
async def test_parse_pdf_date_validation_fixes_inverted_dates() -> None:
    """If LLM returns fecha_reporte < fecha_ocurrencia, it's auto-corrected."""
    pdf_bytes = (_SAMPLES_PDF / "denuncia_policial_robo_001.pdf").read_bytes()
    extracted = {
        "id": "SIN-TEST-999",
        "cobertura": "Daños Materiales",
        "asegurado": "Test Asegurado",
        "ciudad": "Quito",
        "fecha_ocurrencia": "2026-05-10",
        "fecha_reporte": "2026-05-01",  # WRONG: before ocurrencia
        "monto_reclamado": 1000.0,
        "suma_asegurada": 5000.0,
        "descripcion": "Test",
    }
    llm = _make_llm(extracted)
    claims = await parse_pdf(pdf_bytes, llm=llm)
    claim = claims[0]
    # fecha_reporte must be >= fecha_ocurrencia
    assert claim.fecha_reporte >= claim.fecha_ocurrencia


@pytest.mark.asyncio
async def test_parse_pdf_negative_amount_clamped_to_zero() -> None:
    """If LLM returns a negative monto_reclamado, it's clamped to 0."""
    pdf_bytes = (_SAMPLES_PDF / "boleta_siniestro_003.pdf").read_bytes()
    extracted = {
        "id": "SIN-TEST-888",
        "cobertura": "Daños",
        "asegurado": "Test Asegurado",
        "ciudad": "Guayaquil",
        "fecha_ocurrencia": "2026-04-15",
        "fecha_reporte": "2026-04-15",
        "monto_reclamado": -500.0,  # WRONG: negative
        "suma_asegurada": 8000.0,
        "descripcion": "Test monto negativo",
    }
    llm = _make_llm(extracted)
    claims = await parse_pdf(pdf_bytes, llm=llm)
    assert claims[0].monto_reclamado == 0.0


@pytest.mark.asyncio
async def test_parse_docx_blank_raises_value_error() -> None:
    """A .docx with no paragraph text raises ValueError."""
    import docx as _docx
    buf = io.BytesIO()
    doc = _docx.Document()
    doc.add_paragraph("")  # empty paragraph
    doc.save(buf)
    blank_docx = buf.getvalue()

    llm = InMemoryFakeLLM()
    with pytest.raises(ValueError, match="vacío|texto suficiente"):
        await parse_docx(blank_docx, llm=llm)
