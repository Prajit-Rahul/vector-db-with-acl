"""Database access layer for ACL-aware semantic retrieval."""

from __future__ import annotations

import math
from uuid import UUID

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ..core.errors import NotFoundError, ValidationError
from ..core.schemas import SearchResultChunk, UserContext

GET_USER_CONTEXT_SQL = """
SELECT
    u.user_id,
    u.tenant_id,
    COALESCE(array_remove(array_agg(ug.group_id), NULL), ARRAY[]::uuid[]) AS group_ids
FROM app_users u
LEFT JOIN user_groups ug
    ON ug.tenant_id = u.tenant_id
   AND ug.user_id = u.user_id
WHERE u.tenant_id = %s
  AND u.user_id = %s
  AND u.is_active = TRUE
GROUP BY u.user_id, u.tenant_id;
"""

INSERT_CHUNK_SQL = """
INSERT INTO document_chunks (
    tenant_id,
    document_id,
    chunk_index,
    content,
    embedding,
    token_count,
    metadata
)
SELECT
    %s,
    %s,
    %s,
    %s,
    %s::vector,
    %s,
    %s::jsonb
WHERE EXISTS (
    SELECT 1
    FROM documents d
    WHERE d.tenant_id = %s
      AND d.document_id = %s
)
RETURNING chunk_id;
"""

CHUNK_EXISTS_SQL = """
SELECT 1
FROM document_chunks
WHERE tenant_id = %s
  AND chunk_id = %s;
"""

USER_EXISTS_SQL = """
SELECT 1
FROM app_users
WHERE tenant_id = %s
  AND user_id = %s;
"""

VALID_GROUP_IDS_SQL = """
SELECT group_id
FROM groups
WHERE tenant_id = %s
  AND group_id = ANY(%s::uuid[]);
"""

DELETE_USER_GROUPS_SQL = """
DELETE FROM user_groups
WHERE tenant_id = %s
  AND user_id = %s;
"""

INSERT_USER_GROUPS_SQL = """
INSERT INTO user_groups (tenant_id, user_id, group_id)
SELECT %s, %s, src.group_id
FROM unnest(%s::uuid[]) AS src(group_id)
ON CONFLICT (tenant_id, user_id, group_id) DO NOTHING
RETURNING group_id;
"""

ASSIGN_CHUNK_ACL_SQL = """
INSERT INTO chunk_acl_groups (tenant_id, chunk_id, group_id, is_allowed)
SELECT %s, %s, src.group_id, TRUE
FROM unnest(%s::uuid[]) AS src(group_id)
ON CONFLICT (tenant_id, chunk_id, group_id)
DO UPDATE SET is_allowed = EXCLUDED.is_allowed
RETURNING group_id;
"""

DELETE_CHUNK_ACL_SQL = """
DELETE FROM chunk_acl_groups
WHERE tenant_id = %s
  AND chunk_id = %s;
"""

SECURE_SEARCH_SQL = """
SELECT
    c.chunk_id,
    c.document_id,
    c.chunk_index,
    c.content,
    c.metadata,
    1 - (c.embedding <=> %s::vector) AS similarity
FROM document_chunks c
WHERE c.tenant_id = %s
  AND EXISTS (
      SELECT 1
      FROM chunk_acl_groups cag
      WHERE cag.chunk_id = c.chunk_id
        AND cag.tenant_id = %s
        AND cag.group_id = ANY(%s::uuid[])
        AND cag.is_allowed = TRUE
  )
ORDER BY c.embedding <=> %s::vector
LIMIT %s;
"""


class AclSearchRepository:
    """Encapsulates all SQL so policy-critical queries stay centralized."""

    def __init__(self, embedding_dimensions: int) -> None:
        self.embedding_dimensions = embedding_dimensions

    def _to_vector_literal(self, embedding: list[float]) -> str:
        if len(embedding) != self.embedding_dimensions:
            raise ValidationError(
                f"Embedding dimension mismatch: expected {self.embedding_dimensions}, "
                f"got {len(embedding)}"
            )

        converted: list[str] = []
        for value in embedding:
            if not isinstance(value, (int, float)):
                raise ValidationError("Embedding values must be numeric")
            as_float = float(value)
            if not math.isfinite(as_float):
                raise ValidationError("Embedding values must be finite")
            converted.append(format(as_float, ".10g"))

        return "[" + ",".join(converted) + "]"

    @staticmethod
    def _dedupe_preserve_order(values: list[UUID]) -> list[UUID]:
        seen: set[UUID] = set()
        deduped: list[UUID] = []
        for value in values:
            if value not in seen:
                deduped.append(value)
                seen.add(value)
        return deduped

    def get_user_context(
        self,
        conn: Connection,
        *,
        tenant_id: UUID,
        user_id: UUID,
    ) -> UserContext:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(GET_USER_CONTEXT_SQL, (tenant_id, user_id))
            row = cur.fetchone()

        if row is None:
            raise NotFoundError("Active user not found in tenant")

        return UserContext(
            user_id=row["user_id"],
            tenant_id=row["tenant_id"],
            group_ids=row["group_ids"] or [],
        )

    def ingest_chunk(
        self,
        conn: Connection,
        *,
        tenant_id: UUID,
        document_id: UUID,
        chunk_index: int,
        content: str,
        embedding: list[float],
        token_count: int | None,
        metadata: dict,
    ) -> int:
        embedding_literal = self._to_vector_literal(embedding)

        with conn.cursor() as cur:
            cur.execute(
                INSERT_CHUNK_SQL,
                (
                    tenant_id,
                    document_id,
                    chunk_index,
                    content,
                    embedding_literal,
                    token_count,
                    Jsonb(metadata),
                    tenant_id,
                    document_id,
                ),
            )
            inserted = cur.fetchone()

        if inserted is None:
            raise NotFoundError("Document not found in tenant")

        return int(inserted[0])

    def assign_chunk_acl(
        self,
        conn: Connection,
        *,
        tenant_id: UUID,
        chunk_id: int,
        group_ids: list[UUID],
    ) -> list[UUID]:
        if not group_ids:
            raise ValidationError("At least one group_id is required")

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(CHUNK_EXISTS_SQL, (tenant_id, chunk_id))
            if cur.fetchone() is None:
                raise NotFoundError("Chunk not found in tenant")

            cur.execute(VALID_GROUP_IDS_SQL, (tenant_id, group_ids))
            rows = cur.fetchall()
            valid_ids = {row["group_id"] for row in rows}

        missing = [gid for gid in group_ids if gid not in valid_ids]
        if missing:
            raise ValidationError(
                f"One or more groups are invalid for tenant: {', '.join(str(g) for g in missing)}"
            )

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(ASSIGN_CHUNK_ACL_SQL, (tenant_id, chunk_id, group_ids))
            assigned = [row["group_id"] for row in cur.fetchall()]

        return assigned

    def replace_user_groups(
        self,
        conn: Connection,
        *,
        tenant_id: UUID,
        user_id: UUID,
        group_ids: list[UUID],
    ) -> list[UUID]:
        target_group_ids = self._dedupe_preserve_order(group_ids)

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(USER_EXISTS_SQL, (tenant_id, user_id))
            if cur.fetchone() is None:
                raise NotFoundError("User not found in tenant")

            if target_group_ids:
                cur.execute(VALID_GROUP_IDS_SQL, (tenant_id, target_group_ids))
                rows = cur.fetchall()
                valid_ids = {row["group_id"] for row in rows}
            else:
                valid_ids = set()

        missing = [gid for gid in target_group_ids if gid not in valid_ids]
        if missing:
            raise ValidationError(
                f"One or more groups are invalid for tenant: {', '.join(str(g) for g in missing)}"
            )

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(DELETE_USER_GROUPS_SQL, (tenant_id, user_id))
            if not target_group_ids:
                return []
            cur.execute(INSERT_USER_GROUPS_SQL, (tenant_id, user_id, target_group_ids))
            assigned = [row["group_id"] for row in cur.fetchall()]

        return assigned

    def replace_chunk_acl_groups(
        self,
        conn: Connection,
        *,
        tenant_id: UUID,
        chunk_id: int,
        group_ids: list[UUID],
    ) -> list[UUID]:
        target_group_ids = self._dedupe_preserve_order(group_ids)

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(CHUNK_EXISTS_SQL, (tenant_id, chunk_id))
            if cur.fetchone() is None:
                raise NotFoundError("Chunk not found in tenant")

            if target_group_ids:
                cur.execute(VALID_GROUP_IDS_SQL, (tenant_id, target_group_ids))
                rows = cur.fetchall()
                valid_ids = {row["group_id"] for row in rows}
            else:
                valid_ids = set()

        missing = [gid for gid in target_group_ids if gid not in valid_ids]
        if missing:
            raise ValidationError(
                f"One or more groups are invalid for tenant: {', '.join(str(g) for g in missing)}"
            )

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(DELETE_CHUNK_ACL_SQL, (tenant_id, chunk_id))
            if not target_group_ids:
                return []
            cur.execute(ASSIGN_CHUNK_ACL_SQL, (tenant_id, chunk_id, target_group_ids))
            assigned = [row["group_id"] for row in cur.fetchall()]

        return assigned

    def search_authorized_chunks(
        self,
        conn: Connection,
        *,
        tenant_id: UUID,
        group_ids: list[UUID],
        query_embedding: list[float],
        top_k: int,
    ) -> list[SearchResultChunk]:
        if not group_ids:
            return []

        embedding_literal = self._to_vector_literal(query_embedding)

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                SECURE_SEARCH_SQL,
                (
                    embedding_literal,
                    tenant_id,
                    tenant_id,
                    group_ids,
                    embedding_literal,
                    top_k,
                ),
            )
            rows = cur.fetchall()

        return [
            SearchResultChunk(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                metadata=row["metadata"] or {},
                similarity=float(row["similarity"]),
            )
            for row in rows
        ]
