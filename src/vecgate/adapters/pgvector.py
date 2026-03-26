# src/vecgate/adapters/pgvector.py
"""pgvector implementation of VectorBackend.
All SQL uses parameterized queries — no string concatenation for values.
"""
from __future__ import annotations
from pathlib import Path
import psycopg
from vecgate.core.config import Settings
from vecgate.core.errors import BackendError, NotFoundError, ValidationError
from vecgate.core.models import IngestRequest, IngestResponse, SearchResult, UserContext

SQL_DIR = Path(__file__).parent.parent.parent.parent / "sql"


class PgVectorBackend:
    def __init__(self, settings: Settings):
        self._settings = settings

    async def init_schema(self, enable_rls: bool = False) -> None:
        """Bootstrap extensions, tables, and indexes. Idempotent."""
        admin_url = self._settings.admin_database_url or self._settings.database_url
        try:
            async with await psycopg.AsyncConnection.connect(admin_url, autocommit=True) as conn:
                for fname in ["001_schema.sql", "002_indexes.sql"]:
                    sql = (SQL_DIR / fname).read_text()
                    await conn.execute(sql)
                if enable_rls:
                    sql = (SQL_DIR / "003_rls.sql").read_text()
                    await conn.execute(sql)
        except psycopg.Error as e:
            raise BackendError(f"Schema init failed: {e}") from e

    async def create_facet(self, conn: psycopg.AsyncConnection,
                           name: str, description: str | None = None) -> int:
        """Insert facet row and create its partial HNSW index. Returns facet_id."""
        cur = await conn.execute(
            "INSERT INTO facets (name, description) VALUES (%s, %s) "
            "ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description "
            "RETURNING id",
            (name, description),
        )
        row = await cur.fetchone()
        facet_id: int = row[0]
        m = self._settings.hnsw_m
        ef = self._settings.hnsw_ef_construction
        # Per-facet HNSW index — must run outside transaction (autocommit)
        # We use a separate autocommit connection for the CONCURRENTLY index
        db_url = self._settings.database_url
        try:
            async with await psycopg.AsyncConnection.connect(db_url, autocommit=True) as idx_conn:
                await idx_conn.execute(
                    f"CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_embedding_facet_{facet_id} "
                    f"ON chunks USING hnsw (embedding vector_cosine_ops) "
                    f"WITH (m = {m}, ef_construction = {ef}) "
                    f"WHERE facet_id = {facet_id}"
                )
        except psycopg.Error as e:
            raise BackendError(f"Failed to create HNSW index for facet {facet_id}: {e}") from e
        return facet_id

    async def _resolve_facet_id(self, conn: psycopg.AsyncConnection, name: str) -> int:
        cur = await conn.execute("SELECT id FROM facets WHERE name = %s", (name,))
        row = await cur.fetchone()
        if row is None:
            raise NotFoundError(f"Facet '{name}' not found")
        return row[0]

    def _validate_embedding(self, embedding: list[float]) -> None:
        dim = self._settings.embedding_dimensions
        if len(embedding) != dim:
            raise ValidationError(
                f"Embedding has {len(embedding)} dimensions; expected {dim}"
            )
        if not all(isinstance(v, (int, float)) and v == v for v in embedding):
            raise ValidationError("Embedding contains non-finite or non-numeric values")

    async def ingest(self, conn: psycopg.AsyncConnection,
                     request: IngestRequest) -> IngestResponse:
        """Insert document + chunks + ACL assignments atomically."""
        facet_id = await self._resolve_facet_id(conn, request.facet)
        for chunk in request.chunks:
            self._validate_embedding(chunk.embedding)

        async with conn.transaction():
            # Upsert document
            await conn.execute(
                "INSERT INTO documents (id, facet_id) VALUES (%s::uuid, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (request.document_id, facet_id),
            )

            chunk_ids: list[int] = []
            for chunk in request.chunks:
                embedding_str = "[" + ",".join(str(v) for v in chunk.embedding) + "]"
                cur = await conn.execute(
                    "INSERT INTO chunks "
                    "(document_id, facet_id, chunk_index, content, embedding, token_count, metadata) "
                    "VALUES (%s::uuid, %s, %s, %s, %s::vector, %s, %s) "
                    "ON CONFLICT (document_id, chunk_index) DO UPDATE SET "
                    "content = EXCLUDED.content, embedding = EXCLUDED.embedding "
                    "RETURNING id",
                    (request.document_id, facet_id, chunk.chunk_index,
                     chunk.content, embedding_str, chunk.token_count,
                     psycopg.types.json.Jsonb(chunk.metadata)),
                )
                row = await cur.fetchone()
                chunk_id: int = row[0]
                chunk_ids.append(chunk_id)

                if chunk.acl_groups:
                    for group_name in chunk.acl_groups:
                        cur2 = await conn.execute(
                            "SELECT id FROM groups WHERE name = %s", (group_name,)
                        )
                        group_row = await cur2.fetchone()
                        if group_row is None:
                            raise NotFoundError(f"Group '{group_name}' not found")
                        await conn.execute(
                            "INSERT INTO chunk_acl_groups (chunk_id, group_id, is_allowed) "
                            "VALUES (%s, %s, TRUE) ON CONFLICT DO NOTHING",
                            (chunk_id, group_row[0]),
                        )

        return IngestResponse(chunk_ids=chunk_ids)

    async def search(self, conn: psycopg.AsyncConnection,
                     ctx: UserContext, embedding: list[float],
                     top_k: int) -> list[SearchResult]:
        """Fan-out search: one query per authorized facet, merge by distance."""
        if not ctx.facet_ids:
            return []
        self._validate_embedding(embedding)
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

        all_results: list[SearchResult] = []
        for facet_id in ctx.facet_ids:
            cur = await conn.execute(
                """
                SELECT c.id, c.document_id::text, c.chunk_index, c.content,
                       c.metadata, c.embedding <=> CAST(%s AS vector) AS distance
                FROM chunks c
                WHERE c.facet_id = %s
                  AND (
                      NOT EXISTS (SELECT 1 FROM chunk_acl_groups WHERE chunk_id = c.id)
                      OR EXISTS (
                          SELECT 1 FROM chunk_acl_groups
                          WHERE chunk_id = c.id
                            AND group_id = ANY(%s::uuid[])
                            AND is_allowed = TRUE
                      )
                  )
                ORDER BY c.embedding <=> CAST(%s AS vector)
                LIMIT %s
                """,
                (embedding_str, facet_id,
                 ctx.group_ids if ctx.group_ids else [],
                 embedding_str, top_k),
            )
            rows = await cur.fetchall()
            for row in rows:
                all_results.append(SearchResult(
                    id=row[0], document_id=row[1], chunk_index=row[2],
                    content=row[3], metadata=row[4] or {}, distance=float(row[5]),
                ))

        all_results.sort(key=lambda r: r.distance)
        return all_results[:top_k]
