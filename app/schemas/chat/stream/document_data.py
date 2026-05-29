from pydantic import BaseModel


class DocumentData(BaseModel):
    titulo: str
    contenido_markdown: str
