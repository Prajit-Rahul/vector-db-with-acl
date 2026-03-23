"""Pydantic models for request/response and domain DTOs."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    tenant_id: UUID
    group_ids: list[UUID]


class IngestRequest(BaseModel):
    """Chunk ingestion payload.

    tenant and user come from auth context; never trust body values for auth scope.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1, max_length=100_000)
    embedding: list[float] = Field(min_length=1)
    token_count: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    acl_group_ids: list[UUID] = Field(min_length=1)


class IngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: int
    assigned_group_ids: list[UUID]


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID | None = None
    query_text: str | None = Field(default=None, min_length=1, max_length=10_000)
    query_embedding: list[float] | None = None
    top_k: int = Field(default=10, ge=1, le=100)

    @model_validator(mode="after")
    def validate_query_source(self) -> "SearchRequest":
        if bool(self.query_text) == bool(self.query_embedding):
            raise ValueError("Provide exactly one of query_text or query_embedding")
        return self


class SearchResultChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: int
    document_id: UUID
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    similarity: float


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    tenant_id: UUID
    top_k: int
    results: list[SearchResultChunk]


class UpdateUserGroupsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_ids: list[UUID] = Field(default_factory=list)


class UpdateUserGroupsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    tenant_id: UUID
    group_ids: list[UUID]


class UpdateChunkAclGroupsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_ids: list[UUID] = Field(default_factory=list)


class UpdateChunkAclGroupsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: int
    tenant_id: UUID
    assigned_group_ids: list[UUID]
