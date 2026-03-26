# src/vecgate/search/sql.py
"""Canonical parameterized SQL for per-facet ACL-controlled search.

Uses per-facet equality predicate (WHERE facet_id = %s) so PostgreSQL
can select the partial HNSW index for that facet. Do NOT replace with
ANY(array) — that would defeat the partial index and cause full-table scans.
"""

PER_FACET_SEARCH_SQL = """
SELECT
    c.id,
    c.document_id::text,
    c.chunk_index,
    c.content,
    c.metadata,
    c.embedding <=> CAST(%s AS vector) AS distance
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
"""
