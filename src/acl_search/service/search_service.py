"""Service layer for ACL-aware semantic search."""

from __future__ import annotations

from uuid import UUID

from psycopg_pool import ConnectionPool

from ..core.errors import ValidationError
from ..core.schemas import SearchResultChunk, UserContext
from ..repository.search_repository import AclSearchRepository


class AclSearchService:
    """Coordinates transactions and enforces service-level validation."""

    def __init__(
        self,
        *,
        pool: ConnectionPool,
        repository: AclSearchRepository,
        max_top_k: int,
    ) -> None:
        self.pool = pool
        self.repository = repository
        self.max_top_k = max_top_k

    # Required API surface from prompt.
    def getUserContext(self, userId: UUID, tenantId: UUID) -> UserContext:
        with self.pool.connection() as conn:
            return self.repository.get_user_context(
                conn,
                user_id=userId,
                tenant_id=tenantId,
            )

    # Required API surface from prompt.
    def ingestChunk(
        self,
        *,
        tenantId: UUID,
        documentId: UUID,
        chunkIndex: int,
        content: str,
        embedding: list[float],
        tokenCount: int | None,
        metadata: dict,
    ) -> int:
        with self.pool.connection() as conn:
            try:
                chunk_id = self.repository.ingest_chunk(
                    conn,
                    tenant_id=tenantId,
                    document_id=documentId,
                    chunk_index=chunkIndex,
                    content=content,
                    embedding=embedding,
                    token_count=tokenCount,
                    metadata=metadata,
                )
                conn.commit()
                return chunk_id
            except Exception:
                conn.rollback()
                raise

    # Required API surface from prompt.
    def assignChunkAcl(
        self,
        *,
        tenantId: UUID,
        chunkId: int,
        groupIds: list[UUID],
    ) -> list[UUID]:
        with self.pool.connection() as conn:
            try:
                assigned = self.repository.assign_chunk_acl(
                    conn,
                    tenant_id=tenantId,
                    chunk_id=chunkId,
                    group_ids=groupIds,
                )
                conn.commit()
                return assigned
            except Exception:
                conn.rollback()
                raise

    def replaceUserGroups(
        self,
        *,
        tenantId: UUID,
        userId: UUID,
        groupIds: list[UUID],
    ) -> list[UUID]:
        with self.pool.connection() as conn:
            try:
                assigned = self.repository.replace_user_groups(
                    conn,
                    tenant_id=tenantId,
                    user_id=userId,
                    group_ids=groupIds,
                )
                conn.commit()
                return assigned
            except Exception:
                conn.rollback()
                raise

    def replaceChunkAclGroups(
        self,
        *,
        tenantId: UUID,
        chunkId: int,
        groupIds: list[UUID],
    ) -> list[UUID]:
        with self.pool.connection() as conn:
            try:
                assigned = self.repository.replace_chunk_acl_groups(
                    conn,
                    tenant_id=tenantId,
                    chunk_id=chunkId,
                    group_ids=groupIds,
                )
                conn.commit()
                return assigned
            except Exception:
                conn.rollback()
                raise

    def ingestChunkWithAcl(
        self,
        *,
        tenantId: UUID,
        documentId: UUID,
        chunkIndex: int,
        content: str,
        embedding: list[float],
        tokenCount: int | None,
        metadata: dict,
        groupIds: list[UUID],
    ) -> tuple[int, list[UUID]]:
        """Atomic variant used by the ingest API to avoid partial writes."""
        with self.pool.connection() as conn:
            try:
                chunk_id = self.repository.ingest_chunk(
                    conn,
                    tenant_id=tenantId,
                    document_id=documentId,
                    chunk_index=chunkIndex,
                    content=content,
                    embedding=embedding,
                    token_count=tokenCount,
                    metadata=metadata,
                )
                assigned = self.repository.assign_chunk_acl(
                    conn,
                    tenant_id=tenantId,
                    chunk_id=chunk_id,
                    group_ids=groupIds,
                )
                conn.commit()
                return chunk_id, assigned
            except Exception:
                conn.rollback()
                raise

    # Required API surface from prompt.
    def searchAuthorizedChunks(
        self,
        *,
        userId: UUID,
        tenantId: UUID,
        queryEmbedding: list[float],
        topK: int,
    ) -> list[SearchResultChunk]:
        if topK <= 0:
            raise ValidationError("topK must be > 0")
        if topK > self.max_top_k:
            raise ValidationError(f"topK exceeds max_top_k={self.max_top_k}")

        # Fast path: if user has no groups, skip vector query entirely.
        user_ctx = self.getUserContext(userId=userId, tenantId=tenantId)
        if not user_ctx.group_ids:
            return []

        with self.pool.connection() as conn:
            return self.repository.search_authorized_chunks(
                conn,
                tenant_id=tenantId,
                group_ids=user_ctx.group_ids,
                query_embedding=queryEmbedding,
                top_k=topK,
            )
