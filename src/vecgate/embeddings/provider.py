# src/vecgate/embeddings/provider.py
from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class StubEmbeddingProvider:
    """Placeholder — raises NotImplementedError on use."""
    async def embed(self, text: str) -> list[float]:
        raise NotImplementedError(
            "Inject a real EmbeddingProvider to use query_text search. "
            "Example: VecGate(db_url=..., embedding_provider=MyProvider())"
        )
