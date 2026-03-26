# src/vecgate/ingest/ingest.py
from __future__ import annotations
import psycopg
import psycopg.types.json
from vecgate.core.errors import NotFoundError, ValidationError
from vecgate.core.models import IngestRequest, IngestResponse


async def ingest_chunks(
    conn: psycopg.AsyncConnection,
    request: IngestRequest,
    embedding_dimensions: int = 1536,
) -> IngestResponse:
    """Atomically insert document, chunks, and ACL assignments."""
    # Resolve facet_id
    cur = await conn.execute("SELECT id FROM facets WHERE name = %s", (request.facet,))
    facet_row = await cur.fetchone()
    if facet_row is None:
        raise NotFoundError(f"Facet '{request.facet}' not found")
    facet_id = facet_row[0]

    # Validate all embeddings before any writes
    for chunk in request.chunks:
        if len(chunk.embedding) != embedding_dimensions:
            raise ValidationError(
                f"Chunk {chunk.chunk_index}: embedding has {len(chunk.embedding)} dims, "
                f"expected {embedding_dimensions}"
            )

    chunk_ids: list[int] = []
    async with conn.transaction():
        # Upsert document
        await conn.execute(
            "INSERT INTO documents (id, facet_id) VALUES (%s::uuid, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (request.document_id, facet_id),
        )

        for chunk in request.chunks:
            emb_str = "[" + ",".join(str(v) for v in chunk.embedding) + "]"
            cur = await conn.execute(
                "INSERT INTO chunks "
                "(document_id, facet_id, chunk_index, content, embedding, token_count, metadata) "
                "VALUES (%s::uuid, %s, %s, %s, %s::vector, %s, %s) "
                "ON CONFLICT (document_id, chunk_index) DO UPDATE SET "
                "content = EXCLUDED.content, embedding = EXCLUDED.embedding "
                "RETURNING id",
                (request.document_id, facet_id, chunk.chunk_index, chunk.content,
                 emb_str, chunk.token_count,
                 psycopg.types.json.Jsonb(chunk.metadata)),
            )
            row = await cur.fetchone()
            chunk_id: int = row[0]
            chunk_ids.append(chunk_id)

            for group_name in chunk.acl_groups:
                cur2 = await conn.execute("SELECT id FROM groups WHERE name = %s", (group_name,))
                g = await cur2.fetchone()
                if g is None:
                    raise NotFoundError(f"Group '{group_name}' not found — create it first")
                await conn.execute(
                    "INSERT INTO chunk_acl_groups (chunk_id, group_id, is_allowed) "
                    "VALUES (%s, %s, TRUE) ON CONFLICT DO NOTHING",
                    (chunk_id, g[0]),
                )

    return IngestResponse(chunk_ids=chunk_ids)
