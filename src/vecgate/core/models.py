# src/vecgate/core/models.py
from __future__ import annotations
from pydantic import BaseModel, ConfigDict

class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    document_id: str
    chunk_index: int
    content: str
    metadata: dict
    distance: float  # cosine distance: 0 = identical, 2 = opposite

class ChunkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str
    embedding: list[float]
    chunk_index: int
    token_count: int | None = None
    metadata: dict = {}
    acl_groups: list[str] = []  # group names; resolved to UUIDs internally

class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str         # UUID string
    facet: str               # facet NAME — resolved to facet_id internally
    chunks: list[ChunkIn]

class IngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_ids: list[int]

class UserContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int
    facet_ids: list[int]    # never None — empty list means no access
    group_ids: list[str]    # never None — UUID strings; empty list is valid
