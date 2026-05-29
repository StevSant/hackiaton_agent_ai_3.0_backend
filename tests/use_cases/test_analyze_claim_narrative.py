import pytest

from app.infrastructure.llm.fake_llm import InMemoryFakeLLM
from app.schemas.narrative_analysis import NarrativeAnalysis
from app.use_cases.analyze_claim_narrative import analyze_claim_narrative

pytestmark = pytest.mark.asyncio


async def test_analyze_returns_structured_entities_and_coherence() -> None:
    # The user payload embeds the descripcion, so key the canned dict on a substring.
    scripted = {
        "entidades": {
            "personas": ["Juan Pérez"],
            "lugares": ["Av. 9 de Octubre, Guayaquil"],
            "fechas": ["12/03"],
            "vehiculos": ["Toyota Corolla ABC-1234"],
            "terceros": ["otro conductor"],
            "montos": ["$8.000"],
        },
        "narrativa_ilogica": True,
        "incoherencias": ["El vehículo viaja a 200 km/h en zona urbana"],
        "resumen_narrativa": "Colisión declarada en Guayaquil con datos inconsistentes.",
    }
    llm = InMemoryFakeLLM(script={"colisión": scripted})

    result = await analyze_claim_narrative(
        "Hubo una colisión en Guayaquil; el auto iba a 200 km/h por la avenida.",
        llm=llm,
        llm_model="fake",
    )

    assert isinstance(result, NarrativeAnalysis)
    assert result.narrativa_ilogica is True
    assert result.entidades.personas == ["Juan Pérez"]
    assert result.incoherencias == ["El vehículo viaja a 200 km/h en zona urbana"]
    assert "Guayaquil" in result.resumen_narrativa


async def test_analyze_coherent_narrative_has_no_incoherences() -> None:
    scripted = {
        "entidades": {"lugares": ["Quito"]},
        "narrativa_ilogica": False,
        "incoherencias": [],
        "resumen_narrativa": "Choque leve reportado en Quito sin inconsistencias.",
    }
    llm = InMemoryFakeLLM(script={"choque": scripted})

    result = await analyze_claim_narrative(
        "Choque leve en una intersección de Quito, sin heridos.",
        llm=llm,
        llm_model="fake",
    )

    assert result.narrativa_ilogica is False
    assert result.incoherencias == []
    # Unspecified entity buckets default to empty lists, not None.
    assert result.entidades.personas == []
    assert result.entidades.lugares == ["Quito"]
