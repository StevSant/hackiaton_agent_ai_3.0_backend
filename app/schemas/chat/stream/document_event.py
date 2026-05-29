from typing import Literal

from pydantic import BaseModel

from app.schemas.chat.stream.document_data import DocumentData


class DocumentEvent(BaseModel):
    type: Literal["document"] = "document"
    data: DocumentData
