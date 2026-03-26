# src/vecgate/acl/facet.py
from __future__ import annotations
import psycopg
from vecgate.core.config import Settings
from vecgate.core.errors import BackendError


async def create_facet_with_index(
    conn: psycopg.AsyncConnection,
    name: str,
    description: str | None,
    settings: Settings,
) -> int:
    """Insert facet row and create its per-facet partial HNSW index."""
    cur = await conn.execute(
        "INSERT INTO facets (name, description) VALUES (%s, %s) "
        "ON CONFLICT (name) DO UPDATE SET description = COALESCE(EXCLUDED.description, facets.description) "
        "RETURNING id",
        (name, description),
    )
    row = await cur.fetchone()
    facet_id: int = row[0]
    idx_name = f"idx_chunks_embedding_facet_{facet_id}"
    m = settings.hnsw_m
    ef = settings.hnsw_ef_construction
    # CREATE INDEX CONCURRENTLY must run outside a transaction with autocommit
    db_url = settings.database_url
    try:
        async with await psycopg.AsyncConnection.connect(db_url, autocommit=True) as idx_conn:
            await idx_conn.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {idx_name} "
                f"ON chunks USING hnsw (embedding vector_cosine_ops) "
                f"WITH (m = {m}, ef_construction = {ef}) "
                f"WHERE facet_id = {facet_id}"
            )
    except psycopg.Error as e:
        raise BackendError(f"Failed to create HNSW index for facet {facet_id}: {e}") from e
    return facet_id
