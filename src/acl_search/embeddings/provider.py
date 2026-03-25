"""Embedding provider abstraction.

The search API supports either:
1) direct query embeddings from callers, or
2) query text that this layer sends to your embedding stack.
"""

import math
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


def build_deterministic_embedding(text: str, dimensions: int) -> list[float]:
    """Generate deterministic, normalized embedding vectors for local demo flows.

    This is not intended as a semantic-quality model. It provides stable vectors
    so end-to-end ingest/search demos work without external embedding services.
    """
    normalized = text.strip().lower()
    if not normalized:
        raise ValueError("Text is required to generate deterministic embeddings")
    if dimensions <= 0:
        raise ValueError("Embedding dimensions must be > 0")

    vector = [0.0] * dimensions

    for idx, char in enumerate(normalized):
        code = ord(char)
        idx_a = ((code + 31) * 131 + idx * 17) % dimensions
        idx_b = ((code + 7) * 197 + idx * 29) % dimensions
        vector[idx_a] += (code % 29) / 29.0
        vector[idx_b] -= (code % 31) / 31.0

    state = _fnv1a_32(normalized)
    for idx in range(dimensions):
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        noise = ((state & 0xFFFFFFFF) / 0xFFFFFFFF) * 2 - 1
        vector[idx] += noise * 0.04

    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 10) for value in vector]


class DeterministicDemoEmbeddingProvider:
    """Deterministic embedding provider for local UI/E2E runs."""

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def embed_query_text(self, text: str) -> list[float]:
        return build_deterministic_embedding(text, self.dimensions)


def _fnv1a_32(value: str) -> int:
    hash_value = 0x811C9DC5
    for char in value:
        hash_value ^= ord(char)
        hash_value = (hash_value * 0x01000193) & 0xFFFFFFFF
    return hash_value
