from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingsProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
