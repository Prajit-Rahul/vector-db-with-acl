-- secure_search.sql
-- ACL-aware + tenant-aware semantic search in one SQL statement.
-- Inputs:
--   $1 = tenant_id (uuid)
--   $2 = group_ids (uuid array)
--   $3 = query_embedding (vector literal string)
--   $4 = top_k (int)

SELECT
    c.chunk_id,
    c.document_id,
    c.chunk_index,
    c.content,
    c.metadata,
    1 - (c.embedding <=> $3::vector) AS similarity
FROM document_chunks c
WHERE c.tenant_id = $1::uuid
  AND EXISTS (
      SELECT 1
      FROM chunk_acl_groups cag
      WHERE cag.chunk_id = c.chunk_id
        AND cag.tenant_id = $1::uuid
        AND cag.group_id = ANY($2::uuid[])
        AND cag.is_allowed = TRUE
  )
ORDER BY c.embedding <=> $3::vector
LIMIT $4::int;
