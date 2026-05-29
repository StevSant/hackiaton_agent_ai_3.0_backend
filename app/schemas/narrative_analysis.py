"""NarrativeAnalysis — NLP output over a claim's free-text `descripcion`.

Produced by the `analyze_claim_narrative` use case (LLM, structured output).
Covers the spec's NLP sub-capabilities that were missing: entity extraction and
description analysis (logical coherence). The `narrativa_ilogica` verdict is the
genuine NLP source for FS-09 — it is written back into `siniestros.signals` so
the rules engine fires from real analysis, not an external tag.

Framing rule (§2.10): this is *análisis* / *posible incoherencia*, never an
accusation of "fraude".
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedEntities(BaseModel):
    """Structured entities lifted from the narrative (empty lists when none)."""

    personas: list[str] = Field(default_factory=list)
    lugares: list[str] = Field(default_factory=list)
    fechas: list[str] = Field(default_factory=list)
    vehiculos: list[str] = Field(default_factory=list)
    terceros: list[str] = Field(default_factory=list)
    montos: list[str] = Field(default_factory=list)


class NarrativeAnalysis(BaseModel):
    """Full NLP read of the claim narrative: entities + coherence + summary."""

    entidades: ExtractedEntities = Field(default_factory=ExtractedEntities)
    # True when the narrative contains internal logical inconsistencies. Feeds FS-09.
    narrativa_ilogica: bool = False
    # Concrete incoherences found; empty when the narrative is coherent.
    incoherencias: list[str] = Field(default_factory=list)
    # 1-2 sentence neutral summary of what the narrative states.
    resumen_narrativa: str = ""
