"""Embedding provider abstraction.

The search API supports either:
1) direct query embeddings from callers, or
2) query text that this layer sends to your embedding stack.
"""

from typing import Protocol


class EmbeddingProvider(Protocol):
    def embed_query_text(self, text: str) -> list[float]:
        """Return a dense embedding for query text."""


class StubEmbeddingProvider:
    """Stub for environments where embeddings are generated elsewhere."""

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def embed_query_text(self, text: str) -> list[float]:
        raise NotImplementedError(
            "Query-text embedding is not wired yet. Provide query_embedding or "
            "inject a concrete EmbeddingProvider."
        )
