"""Backward-compatible schema exports."""

from .core.schemas import (
    IngestRequest,
    IngestResponse,
    SearchRequest,
    SearchResponse,
    SearchResultChunk,
    UpdateChunkAclGroupsRequest,
    UpdateChunkAclGroupsResponse,
    UpdateUserGroupsRequest,
    UpdateUserGroupsResponse,
    UserContext,
)

__all__ = [
    "UserContext",
    "IngestRequest",
    "IngestResponse",
    "SearchRequest",
    "SearchResultChunk",
    "SearchResponse",
    "UpdateUserGroupsRequest",
    "UpdateUserGroupsResponse",
    "UpdateChunkAclGroupsRequest",
    "UpdateChunkAclGroupsResponse",
]
