"""Tool — genera un documento estructurado (informe/Word) desde el chat.

El LLM construye el contenido en Markdown estructurado; el frontend lo
descarga vía POST /api/v1/agent/document/docx. Este tool no accede a la
base de datos — su única responsabilidad es que el LLM emita un output
tipado con título y contenido.
"""

from pydantic import BaseModel, Field


class CrearDocumentoInput(BaseModel):
    titulo: str = Field(..., min_length=1, description="Título del documento.")
    contenido_markdown: str = Field(
        ...,
        min_length=1,
        description=(
            "Contenido completo en Markdown: encabezados (#/##/###), tablas en "
            "formato pipe (| col | col |), viñetas (- item) y **negrita**. "
            "Cita IDs de siniestros (SIN-XXXX) y códigos de regla (FS-NN/RF-NN). "
            "Nunca uses 'fraude' sin 'posible'."
        ),
    )


class CrearDocumentoOutput(BaseModel):
    titulo: str
    contenido_markdown: str


class CrearDocumentoTool:
    name = "crear_documento"
    description = (
        "Genera un documento estructurado (informe/Word) a partir de la información "
        "de la conversación. Úsalo cuando el analista pida generar/crear un documento, "
        "informe, reporte o Word. Construí el contenido en markdown: título, secciones, "
        "tablas (formato pipe) y viñetas. Cita los IDs de siniestros y reglas relevantes. "
        "Nunca uses la palabra 'fraude' sin 'posible'."
    )

    async def run(self, args: CrearDocumentoInput) -> CrearDocumentoOutput:
        return CrearDocumentoOutput(
            titulo=args.titulo,
            contenido_markdown=args.contenido_markdown,
        )
