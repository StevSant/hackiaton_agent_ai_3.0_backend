from pydantic import BaseModel, Field

from app.schemas.chat.stream.chart_data import ChartType


class ChartHint(BaseModel):
    """Set by the LLM on a chartable tool call ONLY when the user explicitly asked
    for a chart/visualization. The presence of this hint is what triggers a
    `ChartEvent` — its absence means "no chart this turn"."""

    chart_type: ChartType = Field(
        ...,
        description=(
            "Tipo de gráfico solicitado por el analista. "
            "Si pidió 'scatter' / 'dispersión' → scatter. "
            "'barras' → bar. 'barras horizontales' → horizontal_bar. "
            "'torta' / 'pie' → pie. 'dona' / 'doughnut' → doughnut. "
            "'línea' → line. Si no especificó, elegí el más adecuado."
        ),
    )
    title: str | None = Field(
        default=None,
        description="Título opcional. Si se omite, el backend usa un título por defecto.",
        max_length=120,
    )
