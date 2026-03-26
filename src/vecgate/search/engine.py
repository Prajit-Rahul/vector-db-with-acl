# src/vecgate/search/engine.py
from __future__ import annotations
import psycopg
from vecgate.core.errors import ValidationError
from vecgate.core.models import SearchResult, UserContext
from vecgate.search.sql import PER_FACET_SEARCH_SQL


def _embedding_to_str(embedding: list[float]) -> str:
    return "[" + ",".join(str(v) for v in embedding) + "]"


async def fan_out_search(
    conn: psycopg.AsyncConnection,
    ctx: UserContext,
    embedding: list[float],
    top_k: int,
    embedding_dimensions: int = 1536,
) -> list[SearchResult]:
    """Fan-out: one query per authorized facet; merge by ascending distance.

    Returns up to top_k results. Returns [] immediately if user has no facets.
    group_ids is passed as list (never None); empty list means no group memberships
    — open chunks (no chunk_acl_groups rows) are still returned.
    """
    if not ctx.facet_ids:
        return []

    if len(embedding) != embedding_dimensions:
        raise ValidationError(
            f"Embedding has {len(embedding)} dimensions; expected {embedding_dimensions}"
        )

    emb_str = _embedding_to_str(embedding)
    group_ids: list[str] = ctx.group_ids  # always a list, never None

    all_results: list[SearchResult] = []

    for facet_id in ctx.facet_ids:
        cur = await conn.execute(
            PER_FACET_SEARCH_SQL,
            (emb_str, facet_id, group_ids, emb_str, top_k),
        )
        rows = await cur.fetchall()
        for row in rows:
            all_results.append(SearchResult(
                id=row[0],
                document_id=row[1],
                chunk_index=row[2],
                content=row[3],
                metadata=row[4] or {},
                distance=float(row[5]),
            ))

    all_results.sort(key=lambda r: r.distance)
    return all_results[:top_k]
